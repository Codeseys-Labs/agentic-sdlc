#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Derive the ONE terminal activation state from the activation family's emitted artifacts.

ADR-0022 decision 7 says activation ends as **write-ready**, **remediation-ready**, or refused with
exact recovery evidence, and that remediation-ready admits only named hygiene waves and never claims
the repository gate passes. Until this module existed those three words appeared in no tool file at
all: the four operands each answered their own question honestly and nobody composed the answers, so
the state a human acts on was assembled by reading four JSON documents side by side.

    write-ready          normal waves may write
    remediation-ready    only named hygiene waves may write; the gate is KNOWN RED
    refused              no wave may write; the reasons name what is missing

WHY ARTIFACTS AND NOT IMPORTS. The four operands are standalone scripts loaded by absolute path,
two of them with hyphens in their names, one of them a 4,000-line transaction engine that opens file
descriptors and runs Git at import-adjacent depth. Importing across them to reach a predicate would
couple this derivation to their internals and would drag their side conditions into a module whose
entire value is that it has none. So this reads what they PRINT and what they WROTE, exactly as a
human reviewing the chain would, and it re-expresses the two seams it needs rather than importing
them: the activation family's canonical form (sorted, tight, ASCII, one trailing newline) and
`gate_receipt.canonical_json`'s newline-free variant of the same. The journey tests are what keep the
re-expressions honest -- they drive the real producers, so a drifted canonical form surfaces as a
`plan_digest` that will not bind and a `self_digest` that will not re-derive, not as a silent pass.

WHAT EACH STATE REQUIRES. Both ready states require ALL of: an admitted classification (greenfield
or brownfield), the tracked manifest present and clean in the plan's Git projection, a committed
activation receipt at exit 0 whose `plan_digest` binds the supplied plan, every artifact naming the
same target, and every artifact naming the same repository HEAD -- the plan, the activation result,
and the gate receipt each stamp the commit and tree they were derived against, and a chain whose
stamps disagree, or that carries no stamp at all, is refused (see `assess_freshness`). They differ
only in the gate:

    write-ready          the gate receipt's derived `outcome` is `passed`
    remediation-ready    `outcome` is `failed`, the failing set is `identified` (exact NAMES, never
                         `unparsed`), and a `gate_baseline.py` comparison of THIS receipt reports
                         exact non-worsening measured on an undrifted pinned toolchain, against a
                         baseline receipt this module independently reads and confirms is the one
                         the comparison names

A `gate_baseline.py` comparison binds its CANDIDATE side by value already -- the gate label plus
the exact failing set and outcome a consumer compares against its own receipt -- and that needs no
digest. Its BASELINE side used to bind nothing at all: a comparison computed against another
repository's baseline receipt, or a report hand-written to name no receipt whatsoever, read
identically to a genuine one and reached remediation-ready. `gate_baseline.py` now stamps
`baseline_cwd` and `baseline_self_digest` onto every comparison it emits, copied verbatim off the
baseline receipt it verified; this module requires both to be present, requires the stamped `cwd`
to agree with the target every other artifact already agreed on, and requires a `--baseline-receipt`
this module reads for itself whose `self_digest` agrees with the stamp -- so the comparison's claim
about which receipt it baselines is checked against a receipt this module verified on its own, not
merely restated from the comparison's own say-so. A comparison stamped with a foreign `cwd`, a
digest that does not match the supplied receipt, or no stamp at all (the pre-stamp schema) is
refused by name rather than treated as an equally valid baseline: these artifacts are cheap to
regenerate, and admitting an unstamped comparison with a named downgrade would let exactly the gap
this closes keep working for however long an operator's tooling has not been refreshed.

`outcome` partitions {passed, failed, unobserved}, and `unobserved` reaches neither state: a gate
that produced no verdict cannot be evidence that it passed, and it cannot be a baseline either
(`gate_baseline.py` refuses it for the same reason). `unparsed` is not an empty failing set and must
never be compared as one, so it cannot reach remediation-ready however red the gate was.

FAIL CLOSED, AND NAME THE REASON. Anything not provably one of the two ready states is refused, and
every refusal names its own reason, because the audience for a refusal is a human who has to fix
something -- "cannot determine" tells them nothing. An absent artifact is a named reason rather than
a usage error, so this can be run at any point in the chain and will say exactly which evidence is
still missing. Refusing is this module SUCCEEDING at deriving that activation is not ready; it is
not a failure of the query, and that is why it exits 0.

EXITS. Implementation Decision 9 reserves 0 for a valid query or closed requested result, 1 for an
unexpected internal failure, 2 for a grammar/schema/input error, 3 for a clean refusal before
effect, and 4 after an admitted partial or unknown effect. This module's exit space is 0, 2, and 1
only. 3 and 4 are both absent for the same structural reason: **a tool that can cause no effect can
neither refuse before one nor admit one.** Nothing here opens a file for writing, spawns a process,
touches the network, or mutates state; it reads the paths it is given and prints one document. So a
derived `refused` is a result (0) and not a clean refusal (3), and 4 is unreachable rather than
merely unused.

RESIDUALS, STATED EXACTLY.

  * The projection proves NO PENDING CHANGE for the manifest, not that it is TRACKED. The plan's
    `git status --porcelain=v2 -z --untracked-files=all` carries no `--ignored`, so a manifest inside
    a git-ignored path produces no record and reads here exactly like a committed clean one. An
    operator who has ignored `.agentic-sdlc/` does not have tracked portable intent at all, and this
    module cannot see the difference. The one adjacent trap it CAN see is closed: if the activation's
    own `selected_path` is the manifest, the plan's cleanliness proof exempted that path, so the
    projection's silence is an exemption rather than evidence, and that is refused by name.
  * Targets are compared as EXACT STRINGS. A repository reached through a symlinked route, or one
    artifact recorded with a trailing component the others resolved, disagrees and refuses. That is
    the fail-closed half of the trade; resolving paths here would mean touching a filesystem this
    module deliberately only reads through its arguments.
  * A `status` result carries no `plan_digest` (the planner populates it on `plan` and `apply` only),
    so it cannot substitute for the `apply` result. This is deliberate: without that digest the plan
    whose projection is being read is bound to the activation by target alone, and a stale plan from
    an earlier, cleaner tree would pass.
  * The `plan_digest` binding proves only that this apply consumed exactly this plan, and that alone
    never proved the pair was derived against the current tree. That used to be this module's
    loudest residual -- a stale matched plan+apply pair from an earlier, cleaner tree, paired with a
    fresh passing gate receipt, derived write-ready by construction -- and `agentic-sdlc-5ee7`
    closed it: the plan's `git.head`/`git.tree`, the activation result's `head`, and the gate
    receipt's `head` are now compared as ONE anchor by `assess_freshness`, and a chain whose stamps
    disagree, or whose stamp is absent, null, or malformed, is refused by name. What is still NOT
    proven, and is not provable by a module that reads paths and touches no repository, is that the
    agreed head is the CURRENT head; comparing a recorded head against a live one is plan
    admission's job, exactly as `planning-snapshot.py` records for its own seal. That comparison is
    now SHIPPED at that surface rather than merely delegated to it: `agentic-sdlc-187b` added
    `wave-plan-admission.py admit --activation-result`, which reads THIS document's
    `evidence.head_commit`/`head_tree`, requires a `state` that admits a write, and refuses -- naming
    both values -- when either half disagrees with the head the fresh planning snapshot captured
    beside it. The gap therefore closes where wave writes are authorized, not here: this module's own
    answer is unchanged, the flag there is opt-in, and a consumer that composes this state without
    passing it to that gate still holds a head nobody proved current. The anchor is head
    identity and not time because this host's clock legitimately steps backwards
    (agentic-sdlc-184b), so recorded wall time cannot order two artifacts, while head identity is
    deterministic.
  * Every digest check here is RE-DERIVATION, not a security boundary. A same-OS-user forger can
    write a self-consistent receipt, plan, or result; what these checks catch is drift, truncation,
    a hand-edit, and a mismatched pair of artifacts.
  * The gate receipt's full four-state `argv`/`status`/`signal` consistency rule is not re-expressed;
    the two clauses this verdict rests on are (`outcome` must re-derive from `status`, and a verdict
    may not be claimed when nothing was executed). `gate_baseline.py` enforces the rest.

A derived state is evidence about artifacts. It authorizes no push, publication, PR mutation, merge,
or deployment, and write-ready is a statement about the repository's contract surface, not a grant.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import stat
import sys
from pathlib import Path
from typing import Any

RESULT_SCHEMA = "agentic-sdlc/activation-terminal-state@1"

STATE_WRITE_READY = "write-ready"
STATE_REMEDIATION_READY = "remediation-ready"
STATE_REFUSED = "refused"

#: Each state's consequence, verbatim, as ADR-0022 decision 7 and the product spec word it.
CONSEQUENCE = {
    STATE_WRITE_READY: "normal waves may write",
    STATE_REMEDIATION_READY: (
        "only named hygiene waves may write; this result never claims the repository gate passes"
    ),
    STATE_REFUSED: "no wave may write; the reasons and recovery evidence below name what is missing",
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

CLASS_RESULT_SCHEMA = "agentic-sdlc/repository-class-result@1"
CONTRACT_RESULT_SCHEMA = "agentic-sdlc/repository-contract-write-result@1"
PLAN_SCHEMA = "agentic-sdlc/activation-plan@2"
ACTIVATION_RESULT_SCHEMA = "agentic-sdlc/activation-result@3"
BASELINE_SCHEMA = "gate-baseline-comparison/v1"

#: ADR-0022 decision 2's one tracked artifact. Any other path is a different file.
MANIFEST_RELATIVE_PATH = ".agentic-sdlc/repo.toml"

VERDICT_GREENFIELD = "greenfield"
VERDICT_BROWNFIELD = "brownfield"
VERDICT_ASK = "refuse-and-ask"
ADMITTED_VERDICTS = (VERDICT_BROWNFIELD, VERDICT_GREENFIELD)

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_UNOBSERVED = "unobserved"

FAILURES_IDENTIFIED = "identified"

#: Exactly the keys `gate_receipt.build_receipt` writes; `failures` and `head` are the two optional
#: additions. `head` is optional HERE although the current producer always writes it, because a
#: receipt written before the stamp existed must reach a NAMED freshness refusal rather than an
#: exit-2 "not a gate receipt": it is a perfectly well-formed receipt that simply cannot be anchored.
GATE_RECEIPT_OPTIONAL_KEYS = frozenset({"failures", "head"})
GATE_RECEIPT_KEYS = frozenset(
    {"gate", "argv", "status", "signal", "outcome", "log_digest", "toolchain_digest", "cwd", "self_digest"}
)

#: The two keys a head stamp carries, in every artifact that carries one.
HEAD_STAMP_KEYS = frozenset({"commit", "tree"})

#: The two lengths Git writes an object name in (a sha1 and a sha256 repository). Checked against an
#: explicit lowercase-hex alphabet rather than a regular expression's `\d`, which would also admit
#: every Unicode decimal digit and let `٤` pass for a hex character.
OBJECT_NAME_LENGTHS = (40, 64)
HEX_DIGITS = frozenset("0123456789abcdef")


class _Absent:
    """A key that is not there at all, which is NOT the same fact as a key holding null.

    An absent `head` means the artifact was written before its producer stamped heads; a null `head`
    means the producer looked and observed none. Both refuse, and they refuse with different
    reasons, because the fix for the first is "regenerate the artifact" and the fix for the second is
    "find out why no head was readable". Collapsing them into one absence would print the wrong
    instruction for one of the two.
    """


ABSENT = _Absent()

#: One head-stamp classification per artifact, and every one of the four is a distinct reason.
HEAD_ABSENT = "absent"
HEAD_UNOBSERVED = "unobserved"
HEAD_MALFORMED = "malformed"
HEAD_STAMPED = "stamped"

#: The read-only verb that is always legal to run next, for a plane that named no other.
DEFAULT_RECOVER_VERB = "recover inspect"


class InputError(Exception):
    """A supplied artifact is unreadable, unparseable, or not the document it claims to be (exit 2).

    Deliberately separate from a refusal: a malformed artifact means the QUESTION could not be asked,
    while a refusal means it was asked and the answer is "not ready".
    """


def canonical_bytes(value: Any) -> bytes:
    """The activation family's canonical form: sorted keys, tight, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def receipt_canonical_digest(body: dict[str, Any]) -> str:
    """`gate_receipt.canonical_digest`, re-expressed: the same form with NO trailing newline."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN` and `Infinity` by default; no producer here can write one."""
    raise InputError(f"a supplied artifact carries the non-finite JSON constant {token}")


def load_artifact(path: str, label: str) -> dict[str, Any]:
    """Read one emitted artifact. Every failure here is unusable input (exit 2), never a refusal.

    The regular-file check runs BEFORE the read, not as a side effect of one failing: `open()` on a
    FIFO blocks until a writer shows up, which for a supplied artifact path may be never, so a
    directory-instead-of-file mistake would exit 2 promptly while a FIFO-instead-of-file mistake
    hung this process forever. `Path.stat()` follows a symlink to its target rather than reporting
    the link itself, which is the question this module wants answered: "is what I would read a
    regular file", not "is the path itself one".
    """
    candidate = Path(path)
    try:
        mode = candidate.stat().st_mode
    except OSError as exc:
        raise InputError(f"cannot read the {label} artifact {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise InputError(
            f"the {label} artifact {path} is not a regular file, so it cannot be read"
        )
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read the {label} artifact {path}: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=_reject_nonfinite)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"the {label} artifact {path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"the {label} artifact {path} is not a JSON object")
    return value


def require_schema(value: dict[str, Any], key: str, expected: str, label: str, path: str) -> None:
    if value.get(key) != expected:
        raise InputError(f"the {label} artifact {path} is not {expected} ({key}={value.get(key)!r})")


def derive_gate_outcome(status: Any) -> str:
    """`gate_receipt.derive_outcome`, re-expressed. No status can spell `unobserved` but `null`."""
    if status is None:
        return OUTCOME_UNOBSERVED
    return OUTCOME_PASSED if status == 0 else OUTCOME_FAILED


def load_gate_receipt(path: str) -> dict[str, Any]:
    """Read one gate receipt and verify the two clauses this derivation rests on.

    A receipt carries no `schema` field, so it is recognised by its exact key set instead. A receipt
    that predates the `outcome` taxonomy fails that check by name, which is the same answer
    `gate_baseline.py` gives it: what its failing set MEANS cannot be established.
    """
    receipt = load_artifact(path, "gate receipt")
    keys = set(receipt)
    if not GATE_RECEIPT_KEYS <= keys or not keys <= GATE_RECEIPT_KEYS | GATE_RECEIPT_OPTIONAL_KEYS:
        raise InputError(
            f"the gate receipt {path} does not carry exactly a gate receipt's fields, `outcome` "
            f"included: {sorted(keys)}"
        )
    body = {key: value for key, value in receipt.items() if key != "self_digest"}
    if receipt_canonical_digest(body) != receipt["self_digest"]:
        raise InputError(f"the gate receipt {path} does not verify: its self_digest does not re-derive")
    if receipt["outcome"] != derive_gate_outcome(receipt["status"]):
        raise InputError(
            f"the gate receipt {path} records outcome {receipt['outcome']!r}, which its status "
            f"{receipt['status']!r} does not derive"
        )
    if receipt["argv"] is None and receipt["status"] is not None:
        raise InputError(f"the gate receipt {path} claims a verdict although nothing was executed")
    failures = receipt.get("failures")
    if failures is not None and (
        not isinstance(failures, dict)
        or set(failures) != {"harness", "names", "state"}
        or not isinstance(failures["names"], list)
        or not all(isinstance(name, str) for name in failures["names"])
    ):
        raise InputError(f"the gate receipt {path} carries a failing set that is not {{harness, names, state}}")
    return receipt


def porcelain_paths(observation: dict[str, Any], path: str) -> frozenset[str]:
    """Every path the plan's porcelain-v2 -z projection names, decoded and digest-checked.

    A bounded re-expression of the planner's own parser: enough to read WHICH paths carry a record,
    without the duplicate-record and ordering rules that belong to the producer. `-z` means no path
    is quoted, so a record's path is its remaining bytes; a malformed record is unusable input rather
    than an empty answer, because "no record names the manifest" is exactly the conclusion a lossy
    parse would fabricate.
    """
    encoded = observation.get("porcelain_v2_z_base64")
    if not isinstance(encoded, str):
        raise InputError(f"the activation plan {path} carries no porcelain projection")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise InputError(f"the activation plan {path} carries an undecodable porcelain projection: {exc}") from exc
    if hashlib.sha256(raw).hexdigest() != observation.get("porcelain_sha256"):
        raise InputError(f"the activation plan {path} carries a porcelain projection whose digest does not re-derive")
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    malformed = f"the activation plan {path} carries a malformed porcelain record"
    found: set[str] = set()
    index = 0
    while index < len(fields):
        record = fields[index]
        consumed = 1
        kind = record[:1]
        if kind in {b"?", b"!"}:
            if record[1:2] != b" " or not record[2:]:
                raise InputError(malformed)
            paths = [record[2:]]
        elif kind == b"1":
            parts = record.split(b" ", 8)
            if len(parts) != 9 or not parts[8]:
                raise InputError(malformed)
            paths = [parts[8]]
        elif kind == b"2":
            parts = record.split(b" ", 9)
            if len(parts) != 10 or not parts[9] or index + 1 >= len(fields) or not fields[index + 1]:
                raise InputError(malformed)
            # A rename names two paths and the origin sits in the FOLLOWING nul-separated field.
            paths = [parts[9], fields[index + 1]]
            consumed = 2
        elif kind == b"u":
            parts = record.split(b" ", 10)
            if len(parts) != 11 or not parts[10]:
                raise InputError(malformed)
            paths = [parts[10]]
        else:
            raise InputError(malformed)
        found.update(item.decode("utf-8", "surrogateescape") for item in paths)
        index += consumed
    return frozenset(found)


def is_object_name(value: Any) -> bool:
    """True iff `value` is a lowercase-hex Git object name of one of the two lengths Git writes."""
    return isinstance(value, str) and len(value) in OBJECT_NAME_LENGTHS and set(value) <= HEX_DIGITS


def classify_head(value: Any) -> tuple[str, dict[str, str] | None]:
    """Classify one artifact's head stamp, and return its exact value only when it is usable.

    A malformed stamp is its own classification rather than a value that happens to compare unequal
    to every honest one: `{"commit": true}` would otherwise be reported as a head that MOVED, which
    sends a reader looking for a rebase that never happened.
    """
    if isinstance(value, _Absent):
        return HEAD_ABSENT, None
    if value is None:
        return HEAD_UNOBSERVED, None
    if not isinstance(value, dict) or set(value) != HEAD_STAMP_KEYS:
        return HEAD_MALFORMED, None
    if not all(is_object_name(value[key]) for key in sorted(HEAD_STAMP_KEYS)):
        return HEAD_MALFORMED, None
    return HEAD_STAMPED, {"commit": value["commit"], "tree": value["tree"]}


def plan_head_value(plan: dict[str, Any]) -> Any:
    """The plan's head stamp, read from the flat `git.head`/`git.tree` pair it already carried.

    The plan is the one operand that did not need a new field: `capture_git_observation` has always
    recorded the commit and the tree it observed. What it did not have was anybody comparing them to
    anything, which is why the residual this closes described the pair as sharing NO anchor. Reading
    the two flat keys into the same `{commit, tree}` shape the other two artifacts stamp is what
    makes one comparison possible over all three.
    """
    git = plan.get("git")
    if not isinstance(git, dict) or "head" not in git or "tree" not in git:
        return ABSENT
    return {"commit": git["head"], "tree": git["tree"]}


class Assessment:
    """The accumulating evidence. Nothing here decides; `state` derives from `reasons` and the gate."""

    def __init__(self) -> None:
        self.reasons: list[str] = []
        self.target: str | None = None
        self.verdict: str | None = None
        self.outcome: str | None = None
        self.recovery = {"admitted_effects": [], "activation_reasons": [], "recover_verbs": []}
        self.evidence: dict[str, Any] = {
            "activation_command": None,
            "activation_operation_id": None,
            "activation_receipt_digest": None,
            "activation_status": None,
            "baseline_cwd": None,
            "baseline_non_worsening": None,
            "baseline_self_digest": None,
            "baseline_toolchain_drifted": None,
            "gate": None,
            "gate_failing_tests": None,
            # The derived freshness anchor, and populated ONLY when every supplied operand in the
            # chain stamped the same head. On disagreement it stays null and the reasons name both
            # values, because printing one of two disagreeing heads as "the" anchor would present
            # the very ambiguity that refused as if it had been resolved.
            "head_commit": None,
            "head_tree": None,
            "manifest_path": None,
            "manifest_sha256": None,
            "plan_digest": None,
            "plan_selected_path": None,
        }

    def refuse(self, reason: str) -> None:
        self.reasons.append(reason)

    def state(self) -> str:
        """Exactly one state, always.

        The selection is one partition over one value, so two states are unrepresentable. The final
        branch is defence in depth against this module's own worst failure -- returning no state --
        and it is a named refusal rather than an `assert`, which `python -O` would strip.
        """
        if self.reasons:
            return STATE_REFUSED
        if self.outcome == OUTCOME_PASSED:
            return STATE_WRITE_READY
        if self.outcome == OUTCOME_FAILED:
            return STATE_REMEDIATION_READY
        self.refuse(
            f"no terminal state follows from gate outcome {self.outcome!r}, and an underivable "
            "state is refused rather than guessed"
        )
        return STATE_REFUSED


def assess_target(assessment: Assessment, named: list[tuple[str, Any]]) -> None:
    """Bind every artifact to one repository. Composing five artifacts from five trees is the one
    mistake that would let five honest documents add up to a false write-ready."""
    present = [(label, value) for label, value in named if isinstance(value, str) and value]
    if not present:
        return
    assessment.target = present[0][1]
    reference_label, reference = present[0]
    for label, value in present[1:]:
        if value != reference:
            assessment.refuse(
                f"the {label} names a different target ({value}) from the {reference_label} ({reference})"
            )


def assess_classification(assessment: Assessment, classification: dict[str, Any] | None) -> None:
    if classification is None:
        assessment.refuse("no classification result was supplied, so the repository class is unknown")
        return
    assessment.verdict = classification.get("verdict")
    status = classification.get("status")
    reasons = classification.get("reasons") or []
    if status != "classified":
        assessment.refuse(
            f"the classifier did not classify this repository (status {status!r}): "
            + "; ".join(str(item) for item in reasons)
        )
        return
    if assessment.verdict == VERDICT_ASK:
        detail = "; ".join(
            f"{item.get('kind')}: {item.get('detail')}" for item in classification.get("ambiguities") or []
        )
        assessment.refuse(
            f"the classifier returned {VERDICT_ASK}, which is a question and not an admitted class: {detail}"
        )
        return
    if assessment.verdict not in ADMITTED_VERDICTS:
        assessment.refuse(
            f"the classification verdict {assessment.verdict!r} is not one of {list(ADMITTED_VERDICTS)}"
        )


def assess_manifest(
    assessment: Assessment, contract: dict[str, Any] | None, plan: dict[str, Any] | None, plan_path: str | None
) -> None:
    """The tracked manifest must be present, at its one path, and clean in the plan's projection."""
    if contract is None:
        assessment.refuse(
            "no repository contract write result was supplied, so the tracked "
            f"{MANIFEST_RELATIVE_PATH} manifest is not proven present"
        )
    else:
        assessment.evidence["manifest_path"] = contract.get("path")
        assessment.evidence["manifest_sha256"] = contract.get("manifest_sha256")
        status = contract.get("status")
        if status != "written":
            assessment.refuse(
                f"the repository contract manifest was not written (status {status!r}): "
                + "; ".join(str(item) for item in contract.get("reasons") or [])
            )
        elif contract.get("path") != MANIFEST_RELATIVE_PATH:
            assessment.refuse(
                f"the contract manifest was written to {contract.get('path')!r}, not the tracked "
                f"{MANIFEST_RELATIVE_PATH} ADR-0022 decision 2 names"
            )
    if plan is None:
        assessment.refuse(
            "no activation plan was supplied, so the manifest's Git projection cannot be read"
        )
        return
    selected = plan.get("selected_path")
    assessment.evidence["plan_selected_path"] = selected
    if selected == MANIFEST_RELATIVE_PATH:
        assessment.refuse(
            f"the activation's selected path is {MANIFEST_RELATIVE_PATH} itself, which exempts the "
            "manifest from the plan's cleanliness proof, so the projection's silence proves nothing"
        )
    recorded = porcelain_paths(plan.get("git") or {}, str(plan_path))
    if MANIFEST_RELATIVE_PATH in recorded:
        assessment.refuse(
            f"the tracked manifest {MANIFEST_RELATIVE_PATH} carries a pending Git record in the "
            "plan's projection, so it is not clean in the Git projection"
        )


def assess_activation(
    assessment: Assessment, activation: dict[str, Any] | None, plan: dict[str, Any] | None
) -> None:
    """A committed activation receipt at exit 0, bound by digest to the plan just read."""
    if activation is None:
        assessment.refuse("no activation result was supplied, so no committed activation receipt exists")
        return
    assessment.evidence["activation_command"] = activation.get("command")
    assessment.evidence["activation_status"] = activation.get("status")
    assessment.evidence["activation_operation_id"] = activation.get("operation_id")
    assessment.evidence["activation_receipt_digest"] = activation.get("receipt_digest")
    assessment.evidence["plan_digest"] = activation.get("plan_digest")
    status = activation.get("status")
    code = activation.get("exit_code")
    if status != "committed" or code != 0:
        # Recovery evidence is carried VERBATIM from the planner: its reasons, the effects it
        # admitted, and the verbs it says are legal. Paraphrasing any of the three would put this
        # module's guess about somebody else's partial state in front of the operator.
        assessment.recovery["admitted_effects"] = list(activation.get("admitted_effects") or [])
        assessment.recovery["activation_reasons"] = list(activation.get("reasons") or [])
        assessment.recovery["recover_verbs"] = list(activation.get("legal_recovery") or []) or [
            DEFAULT_RECOVER_VERB
        ]
    if status != "committed":
        assessment.refuse(
            f"the activation is not committed (status {status!r}, effect {activation.get('effect')!r})"
        )
    elif code != 0:
        assessment.refuse(f"the activation reports status committed at exit {code}, not exit 0")
    if plan is None:
        return  # `assess_manifest` already refused the absent plan; one reason per fact.
    digest = activation.get("plan_digest")
    if not digest:
        assessment.refuse(
            "the activation result carries no plan_digest, so the supplied plan cannot be bound to "
            "it; a `status` result never carries one, so supply the `apply` result"
        )
    elif digest != hashlib.sha256(canonical_bytes(plan)).hexdigest():
        assessment.refuse(
            "the activation result's plan_digest does not bind the supplied plan, so the Git "
            "projection just read belongs to a different plan"
        )


def _render_head(value: dict[str, str]) -> str:
    """One head, rendered for a human reading a refusal. Both halves, because either can differ."""
    return f"commit {value['commit']} tree {value['tree']}"


def assess_freshness(
    assessment: Assessment,
    plan: dict[str, Any] | None,
    activation: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
) -> None:
    """Bind every operand to ONE repository head, so a stale chain cannot compose into write-ready.

    This is the durable closure of the residual this module used to carry as a known hole: a matched
    plan+apply pair from an earlier, cleaner tree, paired with a fresh passing gate receipt, derived
    write-ready by construction because no operand carried an anchor a read-only composer could
    check. `plan_digest` bound the pair to each other and `cwd`/target bound everything to one path,
    but nothing bound any of it to a POINT IN THE REPOSITORY'S HISTORY (agentic-sdlc-5ee7).

    WHY HEAD IDENTITY AND NOT TIME. A timestamp is the obvious anchor and it is the wrong one on
    this host: the clock legitimately steps backwards (agentic-sdlc-184b), so "the receipt is newer
    than the plan" is not a decidable question from recorded wall time, and an artifact ordering
    built on it would refuse honest chains and admit dishonest ones by turns. Head identity is
    deterministic: two artifacts either name the same commit and tree or they do not, and no clock
    is consulted to find out.

    WHAT THIS DOES AND DOES NOT PROVE. It proves the operands were derived against the SAME tree.
    It does not prove that tree is the CURRENT one -- this module reads paths and touches no
    repository, so "still current" is unanswerable here and is the plan-admission check's job, in
    exactly the split `planning-snapshot.py` records for its own seal. That check exists:
    `wave-plan-admission.py admit --activation-result` compares the anchor recorded below against the
    head a fresh planning snapshot observed (agentic-sdlc-187b). What THIS function closes is the gap
    where three artifacts from two different trees composed into one verdict.

    FAIL CLOSED, FOUR WAYS, EACH NAMED. An operand whose stamp is absent predates the stamp and is
    refused rather than exempted: these artifacts are regenerable, and admitting an unstamped one
    with a named downgrade would keep the whole gap working for however long an operator's tooling
    lagged (the agentic-sdlc-de3a precedent, applied again). A null stamp is a producer that looked
    and saw no head. A malformed stamp is neither. And two well-formed stamps that disagree are the
    stale pair itself, refused with BOTH values printed, because a reader has to see which artifact
    to regenerate.
    """
    operands: list[tuple[str, str, str, dict[str, str] | None]] = []
    if plan is not None:
        state, value = classify_head(plan_head_value(plan))
        operands.append(("activation plan", "git.head/git.tree", state, value))
    if activation is not None:
        state, value = classify_head(activation.get("head", ABSENT))
        operands.append(("activation result", "head", state, value))
    if receipt is not None:
        state, value = classify_head(receipt.get("head", ABSENT))
        operands.append(("gate receipt", "head", state, value))
    # An absent ARTIFACT is not an unstamped one, and it already has its own named reason from the
    # assessor that owns it -- one reason per fact, as `assess_activation` puts it.
    for label, field, state, _ in operands:
        if state == HEAD_ABSENT:
            assessment.refuse(
                f"the {label} carries no {field} head stamp, so it predates repository-head "
                "freshness binding and cannot be proven to describe the same tree as the artifacts "
                f"beside it; re-produce the {label}"
            )
        elif state == HEAD_UNOBSERVED:
            assessment.refuse(
                f"the {label} records a null head stamp, so its producer observed no repository "
                "head at all and this chain cannot be anchored to one tree"
            )
        elif state == HEAD_MALFORMED:
            assessment.refuse(
                f"the {label}'s head stamp is not a {sorted(HEAD_STAMP_KEYS)} pair of Git object "
                "names, so what tree it claims cannot be established"
            )
    stamped = [(label, value) for label, _, state, value in operands if state == HEAD_STAMPED and value is not None]
    if not stamped:
        return
    # Same idiom as `assess_target`: one reference, every other operand compared against it. Equality
    # is transitive, so this refuses a pair that disagrees with each other and a pair that disagrees
    # with the gate receipt's, which is the whole closed set the seed's decision names.
    reference_label, reference = stamped[0]
    agreed = True
    for label, value in stamped[1:]:
        if value != reference:
            agreed = False
            assessment.refuse(
                f"the {label} was derived against a different repository head "
                f"({_render_head(value)}) from the {reference_label} ({_render_head(reference)}), so "
                "these artifacts describe two different trees and one of them is stale"
            )
    if agreed and len(stamped) == len(operands):
        # The anchor is recorded only when it is genuinely derived: every supplied operand stamped a
        # head and they all agree. A chain where one operand refused above has no agreed anchor to
        # report, and reporting the survivors' as one would overstate what was proven.
        assessment.evidence["head_commit"] = reference["commit"]
        assessment.evidence["head_tree"] = reference["tree"]


def assess_gate(
    assessment: Assessment,
    receipt: dict[str, Any] | None,
    baseline: dict[str, Any] | None,
    baseline_receipt: dict[str, Any] | None,
) -> None:
    """The one predicate that separates the two ready states, and the only exact-baseline gate."""
    if receipt is None:
        assessment.refuse("no gate receipt was supplied, so no gate verdict is available")
        return
    assessment.outcome = receipt["outcome"]
    assessment.evidence["gate"] = receipt.get("gate")
    failures = receipt.get("failures")
    if failures is not None:
        assessment.evidence["gate_failing_tests"] = sorted(failures["names"])
    if baseline is not None:
        # Surfaced verbatim off the comparison document, exactly as the two fields above are --
        # including on a path that refuses below, so a human reading a REFUSED result can still see
        # which baseline the comparison named. `gate_baseline.py` stamps these off the receipt IT
        # verified; the checks further down independently re-verify the stamp against
        # `baseline_receipt` before trusting it for the ready/refused decision itself.
        assessment.evidence["baseline_cwd"] = baseline.get("baseline_cwd")
        assessment.evidence["baseline_non_worsening"] = baseline.get("non_worsening")
        assessment.evidence["baseline_self_digest"] = baseline.get("baseline_self_digest")
        assessment.evidence["baseline_toolchain_drifted"] = baseline.get("toolchain_drifted")
    if assessment.outcome == OUTCOME_UNOBSERVED:
        assessment.refuse(
            "the gate produced no verdict (outcome unobserved), so it is evidence neither that the "
            "gate passes nor of an exact failing set"
        )
        return
    if assessment.outcome == OUTCOME_PASSED:
        return
    if failures is None:
        assessment.refuse(
            "the gate failed and the receipt records no failing set, so it was never baselined: "
            "re-record the gate with --harness unittest"
        )
        return
    if failures["state"] != FAILURES_IDENTIFIED:
        assessment.refuse(
            f"the gate receipt's failing set is {failures['state']}: identification was attempted "
            "and failed, which is not an exact set of names and cannot be remediated against"
        )
        return
    if baseline is None:
        assessment.refuse(
            "no baseline comparison was supplied, so the failing set is known but not proven "
            "non-worsening; compare it with scripts/gate_baseline.py"
        )
        return
    if baseline.get("gate") != receipt.get("gate"):
        assessment.refuse(
            f"the baseline comparison is about a different gate ({baseline.get('gate')!r}) from the "
            f"receipt ({receipt.get('gate')!r})"
        )
        return
    if sorted(baseline.get("candidate_failing") or []) != sorted(failures["names"]) or baseline.get(
        "candidate_outcome"
    ) != assessment.outcome:
        assessment.refuse(
            "the baseline comparison does not compare this gate receipt: its candidate failing set "
            "or candidate outcome differs from the receipt's"
        )
        return
    if baseline.get("toolchain_drifted"):
        assessment.refuse(
            "the baseline comparison was measured under a different pinned toolchain than this "
            "receipt's, so the exact non-worsening comparison remediation-ready rests on is not "
            "exact"
        )
        return
    non_worsening = baseline.get("non_worsening")
    if not isinstance(non_worsening, bool):
        # `newly_failing or not non_worsening` would silently read an absent or mistyped field as
        # "worsened" and print a reason naming no test at all. A comparison that does not STATE
        # non_worsening as a boolean is its own fact -- the exactness question could not be
        # answered -- not a worsened verdict this module invented from a missing field.
        assessment.refuse(
            "the baseline comparison does not state non_worsening as a boolean, so whether it "
            "worsens the baseline cannot be established"
        )
        return
    # Baseline IDENTITY, not just the candidate-side values already checked above. Every check from
    # here down closes the gap `activation-result.py` used to have: a comparison naming no receipt
    # at all -- computed against another repository's baseline, or hand-written altogether -- read
    # identically to a genuine one, because nothing bound the report to the baseline receipt it
    # claimed to compare. `gate_baseline.py` now stamps `baseline_cwd`/`baseline_self_digest`
    # verbatim off the receipt it verified; a report from before that stamp existed carries neither
    # key, and admitting it with a named downgrade would keep the exact gap working for however
    # long an operator's `gate_baseline.py` build lagged this one, so it is refused by name instead.
    if "baseline_cwd" not in baseline or "baseline_self_digest" not in baseline:
        assessment.refuse(
            "the baseline comparison carries no baseline_cwd/baseline_self_digest stamp, so it "
            "predates baseline identity stamping and cannot be bound to a baseline receipt; "
            "re-run scripts/gate_baseline.py compare to produce a stamped comparison"
        )
        return
    stamped_cwd = baseline.get("baseline_cwd")
    if stamped_cwd != assessment.target:
        assessment.refuse(
            f"the baseline comparison's stamped baseline cwd ({stamped_cwd!r}) does not agree with "
            f"the target ({assessment.target!r}), so it may be a comparison against another "
            "repository's baseline receipt"
        )
        return
    if baseline_receipt is None:
        assessment.refuse(
            "no baseline receipt was supplied, so the baseline comparison's stamped "
            "baseline_self_digest cannot be independently verified against the receipt it names"
        )
        return
    if baseline.get("baseline_self_digest") != baseline_receipt.get("self_digest"):
        assessment.refuse(
            "the baseline comparison's stamped baseline_self_digest does not agree with the "
            "supplied baseline receipt's self_digest, so the comparison cannot be trusted to be "
            "about that receipt"
        )
        return
    if baseline_receipt.get("cwd") != assessment.target:
        # Belt and suspenders over the check above: the STAMP could in principle be forged to name
        # this target while the digest genuinely matches a receipt from elsewhere. The receipt this
        # module read for itself is the ground truth, so its own `cwd` is checked directly too.
        assessment.refuse(
            "the independently-read baseline receipt's own cwd "
            f"({baseline_receipt.get('cwd')!r}) does not agree with the target "
            f"({assessment.target!r})"
        )
        return
    # Identity alone (the two checks above) is not arithmetic. A hand-written comparison can stamp
    # a REAL baseline_cwd/baseline_self_digest -- both genuinely bound to the supplied baseline
    # receipt -- while still forging baseline_failing/newly_failing/non_worsening to claim no
    # regression (agentic-sdlc-de3a finding D2, adjudicated as agentic-sdlc-498b). The candidate
    # side already has this property: `failures["names"]` is the receipt's OWN failing set, checked
    # against `baseline.get("candidate_failing")` above. The baseline side gets the same binding
    # here, and `newly_failing` is RECOMPUTED from the two bound sets rather than trusted from the
    # comparison document, so a say-so field can no longer carry the verdict.
    baseline_receipt_failures = baseline_receipt.get("failures")
    if baseline_receipt_failures is None:
        assessment.refuse(
            "the independently-read baseline receipt records no failing set, so the baseline "
            "comparison's baseline_failing cannot be bound to it"
        )
        return
    if baseline_receipt_failures.get("state") != FAILURES_IDENTIFIED:
        assessment.refuse(
            "the independently-read baseline receipt's failing set is "
            f"{baseline_receipt_failures.get('state')!r}: identification was attempted and failed, "
            "so the baseline comparison's arithmetic cannot be bound to it"
        )
        return
    receipt_baseline_failing = sorted(baseline_receipt_failures["names"])
    stamped_baseline_failing = sorted(baseline.get("baseline_failing") or [])
    if stamped_baseline_failing != receipt_baseline_failing:
        assessment.refuse(
            "the baseline comparison's baseline_failing does not agree with the independently-read "
            "baseline receipt's own failing set, so its arithmetic cannot be trusted: "
            + ", ".join(sorted(set(stamped_baseline_failing) ^ set(receipt_baseline_failing)) or ["(unnamed)"])
        )
        return
    recomputed_newly_failing = sorted(set(failures["names"]) - set(receipt_baseline_failing))
    stamped_newly_failing = sorted(baseline.get("newly_failing") or [])
    if stamped_newly_failing != recomputed_newly_failing:
        assessment.refuse(
            "the baseline comparison's newly_failing does not match the set recomputed from the "
            "candidate receipt's and the independently-read baseline receipt's own failing sets: "
            + ", ".join(sorted(set(stamped_newly_failing) ^ set(recomputed_newly_failing)) or ["(unnamed)"])
        )
        return
    if recomputed_newly_failing or not non_worsening:
        assessment.refuse(
            "the candidate worsens the baseline, newly failing: "
            + ", ".join(recomputed_newly_failing or ["(unnamed)"])
        )


def derive_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Load every supplied artifact, then derive exactly one terminal state from them."""
    classification = load_artifact(args.classification, "classification result") if args.classification else None
    if classification is not None:
        require_schema(classification, "schema", CLASS_RESULT_SCHEMA, "classification result", args.classification)
    contract = load_artifact(args.contract, "repository contract write result") if args.contract else None
    if contract is not None:
        require_schema(
            contract, "schema", CONTRACT_RESULT_SCHEMA, "repository contract write result", args.contract
        )
    plan = load_artifact(args.plan, "activation plan") if args.plan else None
    if plan is not None:
        require_schema(plan, "schema", PLAN_SCHEMA, "activation plan", args.plan)
    activation = load_artifact(args.activation, "activation result") if args.activation else None
    if activation is not None:
        require_schema(activation, "schema", ACTIVATION_RESULT_SCHEMA, "activation result", args.activation)
    receipt = load_gate_receipt(args.gate_receipt) if args.gate_receipt else None
    baseline = load_artifact(args.baseline_comparison, "baseline comparison") if args.baseline_comparison else None
    if baseline is not None:
        require_schema(baseline, "schema_version", BASELINE_SCHEMA, "baseline comparison", args.baseline_comparison)
    baseline_receipt = load_gate_receipt(args.baseline_receipt) if args.baseline_receipt else None

    assessment = Assessment()
    assess_target(
        assessment,
        [
            ("classification result", (classification or {}).get("target")),
            ("repository contract write result", (contract or {}).get("target")),
            ("activation plan", ((plan or {}).get("target") or {}).get("path")),
            ("activation result", (activation or {}).get("target")),
            ("gate receipt", (receipt or {}).get("cwd")),
        ],
    )
    assess_classification(assessment, classification)
    assess_manifest(assessment, contract, plan, args.plan)
    assess_activation(assessment, activation, plan)
    assess_gate(assessment, receipt, baseline, baseline_receipt)
    # Last, and deliberately not folded into the three assessors above: freshness is the one question
    # no single artifact can answer, so it is asked of the set rather than of any member. The
    # BASELINE receipt is not an operand here -- a baseline is from an earlier tree by construction,
    # which is what makes it a baseline, so requiring it to name this head would make exact
    # non-worsening comparison impossible on any repository that had moved since.
    assess_freshness(assessment, plan, activation, receipt)

    state = assessment.state()
    result = {
        "schema": RESULT_SCHEMA,
        "command": "derive",
        "state": state,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[state],
        "classification": assessment.verdict,
        "gate_outcome": assessment.outcome,
        "gate_passes": None if assessment.outcome is None else assessment.outcome == OUTCOME_PASSED,
        "target": assessment.target,
        "reasons": assessment.reasons,
        "recovery": assessment.recovery,
        "evidence": assessment.evidence,
    }
    return result, EXIT_OK


def report_input_error(message: str) -> None:
    """Write this module's one diagnostic line through a sink a hostile stderr cannot corrupt.

    Re-expressed from `gate_receipt.py`'s `_guarded_stderr_sink`/`abandon_broken_stream` (mirrored
    rather than imported, per this module's own no-cross-import rule) for this module's single
    diagnostic line. The message is display only -- exit 2 and the absent result document on
    stdout are the evidence -- so a stream that cannot accept it must cost the channel, never the
    classified exit code. Two hostile shapes are not exotic: `2>&-` starts the interpreter with
    `sys.stderr is None`, so an unguarded `sys.stderr.write` raises `AttributeError` and an uncaught
    exception replaces exit 2 with exit 1; a reader that has gone away turns every write into
    `EPIPE` and leaves bytes pending that CPython flushes again while finalizing, which replaces
    exit 2 with exit 120 unless the failed stream is dropped here first.
    """
    stream = sys.stderr
    if stream is None:  # `2>&-`: this process was handed no stderr to be diagnostic on
        return
    try:
        stream.write(f"activation-result.py: {message}\n")
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()
    except (OSError, ValueError):  # EPIPE/ENOSPC, or a stream closed underneath us
        if getattr(sys, "stderr", None) is stream:
            sys.stderr = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="activation-result.py",
        description=(
            "Derive the one terminal activation state -- write-ready, remediation-ready, or "
            "refused -- from the activation family's emitted artifacts. Read-only, offline, "
            "subprocess-free, and effect-free: it authorizes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "derive",
        description=(
            "Every artifact is optional and every absence is a NAMED reason, so this may be run at "
            "any point in the chain and will say which evidence is still missing."
        ),
        epilog=(
            "Exit codes: 0 a terminal state was derived, refused included -- refusing is this "
            "command succeeding at deciding that activation is not ready; 2 a supplied artifact is "
            "unreadable, not JSON, or not the document it claims to be; 1 an unexpected internal "
            "failure. Implementation Decision 9's 3 and 4 do not apply: a command that causes no "
            "effect can neither refuse before one nor admit one."
        ),
    )
    command.add_argument("--classification", default=None, help="repository-classifier.py classify result")
    command.add_argument("--contract", default=None, help="repository-contract-writer.py write result")
    command.add_argument("--plan", default=None, help="activation-planner.py plan document")
    command.add_argument("--activation", default=None, help="activation-planner.py apply result")
    command.add_argument("--gate-receipt", dest="gate_receipt", default=None, help="gate_receipt.py record receipt")
    command.add_argument(
        "--baseline-comparison",
        dest="baseline_comparison",
        default=None,
        help="gate_baseline.py compare report; only a failed gate needs one",
    )
    command.add_argument(
        "--baseline-receipt",
        dest="baseline_receipt",
        default=None,
        help=(
            "the gate_receipt.py receipt --baseline-comparison was computed against; required to "
            "independently verify the comparison's stamped baseline identity"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result, code = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    sys.stdout.buffer.write(canonical_bytes(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
