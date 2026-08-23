#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Admit or refuse a `RuntimeAssignment` before spawn, and classify what a receipt actually served.

Two questions, one read-only tool, because they are the two halves of one contract: the root
`AGENTS.md` paragraph beginning "Before spawn, the conductor supplies a certified `RuntimeAssignment`"
and issue 07's completion condition that "runtime receipts contain no unexplained substitution".

    admit      one `RuntimeAssignment` before spawn -> admit-dispatch | refuse-dispatch | seed-proposal
    classify   one served record against its request -> exact-match | explained-substitution |
               unexplained-substitution

WHAT EACH VERDICT MEANS.

    admit-dispatch            every admission clause is affirmatively satisfied; the conductor may
                              proceed to spawn. Admission is evidence about an assignment, never
                              authority for an outward effect.
    refuse-dispatch           a clause fails. The assignment stops before dispatch and therefore
                              before spawn, and every reason names what was missing.
    seed-proposal             the selected host or launcher cannot inject BOTH the exact model and
                              the exact effort. The contract's answer to that is not a refusal note
                              but one `SeedProposal`, so this verdict carries the typed proposal.
    exact-match               the served route and every observed effective value equal the request.
    explained-substitution    a difference is covered by a documented fallback inside the approved
                              envelope, and that entry NAMES its authorization.
    unexplained-substitution  anything else, INCLUDING anything unprovable. This blocks wave
                              completion, so it is the fail-closed sink: a difference nobody can
                              explain and a difference nobody can observe are the same blocker.

WHY THE CONFLATION GUARDS ARE THE POINT. The contract separates four fact classes that all look
alike in a JSON document and are catastrophic to merge:

  * the requested semantic TIER and the resolved exact provider/model are separate facts;
  * a requested value is a request, never proof, however it is spelled;
  * request injection evidence proves what was SENT; readback evidence proves what was OBSERVED;
  * an honestly unavailable effective readback is its own fact and never becomes the requested value.

So this refuses an assignment whose tier field holds a model ID, an assignment whose resolved
identity field holds a tier name, and a "verified" effort or context readback whose bytes are a
request echo -- the last is the most dangerous input in the space, because a receipt that copies its
requested values into its readback fields is structurally COMPLETE and reads as fully resolved.

WHY A WRAPPER DOCUMENT. `admit` reads one `agentic-sdlc/runtime-admission-request@1` document that
embeds the `runtime-assignment-receipt/v1` assignment VERBATIM, alongside the two graph-level facts
the pinned receipt schema has no field for: the requested semantic tier and the host's injection
capability. That keeps the embedded bytes byte-compatible with what
`skills/model-tier-rightsizing/scripts/receipt_admission.py` validates, so the two tools compose
without either changing shape. The division of labour is deliberate: `receipt_admission.py` owns
exhaustive canonical-consistency validation of the receipt (closed field sets, certified tuples,
every evidence digest); this tool owns the ADMISSION VERDICT and re-checks only the clauses that
verdict rests on. Run both; neither subsumes the other, and this one never reports a receipt as
canonically valid.

WHY IT IMPORTS NEITHER OPERAND. `receipt_admission.py` lives in another skill's tree and reads its
policy from its own `__file__`; the activation family's tools are hyphen-named scripts loaded by
path. This module re-expresses rather than imports the two seams it needs --
`receipt_admission.canonical_json`'s newline-free `ensure_ascii=False` form for every receipt-side
digest, and the activation family's sorted/tight/ASCII/one-trailing-newline form for its own output.
The vocabularies are NOT re-expressed: the allowed efforts, context forms, and the exact model ID ->
provider map are READ from the checked-in policy, so the unambiguity of an exact-ID mapping is a
policy fact rather than this module's opinion.

ONE PARTITION, ONE VERDICT. Predicates only accumulate named reasons; exactly one ordered selection
over the accumulated lists produces the verdict, so no input yields two verdicts or none. Each
clause registers itself as evaluated and the selection refuses when the evaluated set is incomplete,
because this module's worst failure mode is a future early return that silently drops a clause and
admits. A bare "cannot determine" is never emitted: the audience for a refusal is a human who has to
fix something.

SEED-PROPOSAL PRECEDENCE, STATED. When the host cannot inject and some other clause also fails, the
verdict is `seed-proposal` and the other reasons are still listed in the same document. Both outcomes
stop before spawn; the missing injection capability is the one that must be fixed first, and nothing
is hidden by the ordering.

EXITS. Implementation Decision 9 reserves 0 for a valid query or closed requested result, 1 for an
unexpected internal failure, 2 for a grammar/schema/input error, 3 for a clean refusal before any
effect, and 4 after an admitted partial or unknown effect. This module's exit space is 0, 2, and 1
only. 3 and 4 are both absent for the same structural reason: **a tool that can cause no effect can
neither refuse before one nor admit one.** Nothing here opens a file for writing, spawns a process,
reads a clock, or touches the network; it reads the paths it is given and prints one document. So a
derived `refuse-dispatch`, `seed-proposal`, or `unexplained-substitution` is a RESULT (0) and not a
clean refusal (3), and 4 is unreachable rather than merely unused.

A HOSTILE STREAM MAY NOT MOVE THAT EXIT CODE, and the two streams are not the same kind of thing.
Stderr is display only, so a grammar error, a schema refusal, and a derived verdict each keep their
code whether stderr is absent (`2>&-`), broken (`EPIPE`), or working -- and a grammar error puts no
bytes on stdout in any of those cases, because usage that fell back to stdout would occupy the one
channel a result document lives on. Stdout is the evidence, so a stdout that cannot receive the
result document is exit 1: the verdict was derived and not delivered, which is neither a success nor
an input error. Neither stream may leave a failed write pending, because CPython's shutdown flush of
one would replace this module's exit code with 120.

RESIDUALS, STATED EXACTLY.

  * Nothing here authenticates an issuer. Every digest check is RE-DERIVATION: a same-OS-user forger
    can write a self-consistent request document, and what these checks catch is drift, truncation,
    a hand-edit, a transplanted evidence object, and a requested value wearing a readback's clothes.
  * `is_request_echo` refuses the shapes a holder of the request PROVABLY could have written. Bytes
    outside those shapes are recorded, never vouched for; only the external authenticated harness can
    testify that bytes came from a transport.
  * `classify`'s served record is declarative. This module cannot re-derive a transport's bytes from
    a post-hoc record, so it holds the record to source admissibility (a gateway response body is
    refused by name, because it echoes the caller's own request string) and to internal honesty (a
    status of `unavailable` that nonetheless carries a value is the conflation with a different mask).
    That honesty rule binds the MODEL axis exactly as it binds effort and context, because a silent
    gateway fallback recorded as `model_id` beside an honest `unavailable` is the highest-value place
    in this document to hide a substitution.
  * An authorization entry is checked for a NAMED authority, not for a real one. "authorized_by":
    "the plan" satisfies the shape; whether that plan exists and approved this envelope is the
    conductor's question, and both fields are echoed into the output so a human can check them.
  * The contract says `resolved` is recorded only after adapter readback, yet the same paragraph
    places the certified assignment BEFORE spawn. The two are consistent only if the readback
    testifies to the ROUTE -- established for that exact model/effort/context tuple by the harness
    before this dispatch -- and not to the not-yet-existing child call. This module reads it that
    way; it cannot detect a readback captured from a stale route.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: The sibling skill that OWNS the vocabulary. Resolved from this file so a symlinked host plane
#: lands on the real tree; never from the caller's cwd, environment, or home.
DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
)

ADMISSION_SCHEMA = "agentic-sdlc/runtime-assignment-admission@1"
CLASSIFICATION_SCHEMA = "agentic-sdlc/runtime-substitution-classification@1"
REQUEST_SCHEMA = "agentic-sdlc/runtime-admission-request@1"
SERVED_SCHEMA = "agentic-sdlc/runtime-served-record@1"
RECEIPT_SCHEMA_VERSION = "runtime-assignment-receipt/v1"

VERDICT_ADMIT = "admit-dispatch"
VERDICT_REFUSE = "refuse-dispatch"
VERDICT_SEED = "seed-proposal"

VERDICT_EXACT = "exact-match"
VERDICT_EXPLAINED = "explained-substitution"
VERDICT_UNEXPLAINED = "unexplained-substitution"

ADMISSION_CONSEQUENCE = {
    VERDICT_ADMIT: (
        "the conductor may proceed to spawn this node; admission is evidence about the assignment "
        "and authorizes no outward effect"
    ),
    VERDICT_REFUSE: (
        "this assignment stops before dispatch and therefore before spawn; the reasons below name "
        "what is missing"
    ),
    VERDICT_SEED: (
        "the host cannot inject the exact model and effort, so the contract's output is one "
        "SeedProposal and not a dispatch; no spawn may follow"
    ),
}

CLASSIFICATION_CONSEQUENCE = {
    VERDICT_EXACT: "the receipt records no substitution",
    VERDICT_EXPLAINED: (
        "the receipt records a documented fallback inside the approved envelope, with its "
        "authorization named; wave completion is not blocked by it"
    ),
    VERDICT_UNEXPLAINED: (
        "this blocks wave completion: a wave is complete only when runtime receipts contain no "
        "unexplained substitution"
    ),
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The four semantic tiers `model-tier-rightsizing` owns. A tier is a decision about blast radius;
#: it is never a route, and no member of this set may appear as a resolved provider or model ID.
TIERS = ("frontier", "judgment-workhorse", "capable-volume", "mechanical-floor")

RESOLUTION_RESOLVED = "resolved"
#: The two non-resolved states the contract names, each of which is a request rather than proof.
RESOLUTION_INHERITED = "inherited"
RESOLUTION_UNRESOLVED = "unresolved"
RESOLUTION_REQUESTED = "requested"

STATUS_VERIFIED = "verified"
STATUS_UNAVAILABLE = "unavailable"

BASIS_READBACK = "independent_readback"
BASIS_MAPPING = "unambiguous_exact_id_mapping"

IDENTITY_SOURCE_ADAPTER = "adapter_response_readback"
IDENTITY_SOURCE_GATEWAY_LOG = "gateway_attribution_log"
IDENTITY_SOURCE_GATEWAY_BODY = "gateway_response_body"
ADMISSIBLE_IDENTITY_SOURCES = (IDENTITY_SOURCE_ADAPTER, IDENTITY_SOURCE_GATEWAY_LOG)

MATCHES_REQUESTED = "matches_requested"
DIVERGES_FROM_REQUESTED = "diverges_from_requested"
DIVERGENCE_UNAVAILABLE = "unavailable"

#: The two effective-value axes a transport may or may not expose, and the receipt fields each owns.
EFFECTIVE_AXES = {
    "effort": ("requested_effort", "observed_effort", "allowed_efforts", "effort_effective_divergence"),
    "context": (
        "requested_context_form",
        "observed_context_form",
        "allowed_context_forms",
        "context_effective_divergence",
    ),
}

#: Every clause the admission verdict rests on. The selection refuses if one did not run.
ADMISSION_CLAUSES = frozenset(
    {
        "completeness",
        "resolution_state",
        "tier_separation",
        "request_injection",
        "request_immutability",
        "model_identity",
        "effort_readback",
        "context_readback",
        "host_injection",
    }
)

#: Every axis `classify` must dispose of before it may answer `exact-match`.
CLASSIFICATION_AXES = frozenset({"model", "effort", "context"})

#: The host capability declaration, closed. Booleans must be real booleans: a string "false" that
#: read as truthy would turn an uninjectable host into an admitted dispatch.
HOST_INJECTION_FIELDS = frozenset({"host", "surface", "injects_model", "injects_effort"})

#: The repository's typed `SeedProposal`, re-expressed from the field list the research-os role
#: instructions carry, so an uninjectable assignment leaves as the queue's own shape.
SEED_PROPOSAL_FIELDS = (
    "title",
    "summary",
    "acceptance_criteria",
    "priority",
    "blocking",
    "scope",
    "evidence",
    "dependencies",
    "recommended_owner",
)

#: An authorization entry inside the approved substitution envelope, closed.
AUTHORIZATION_FIELDS = frozenset({"axis", "from", "to", "to_provider", "authorized_by", "approved_in"})

#: Absence sentinel. `None` is a value a document can carry, so it cannot mean "no such field".
MISSING = object()
UNRESOLVED = object()
UNPARSEABLE = object()


class InputError(Exception):
    """A supplied artifact is unreadable, unparseable, or not the document it claims to be (exit 2).

    Deliberately separate from a refusal or an unexplained classification: a malformed artifact means
    the QUESTION could not be asked, while a verdict means it was asked and answered.
    """


def canonical_bytes(value: Any) -> bytes:
    """This module's output form: sorted keys, tight, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def receipt_json(value: Any) -> str:
    """`receipt_admission.canonical_json`, re-expressed: tight, sorted, `ensure_ascii=False`, no newline.

    Kept distinct from `canonical_bytes` on purpose. Every digest that has to agree with a receipt
    the other tool produced is computed through THIS form, and the module's own output through the
    other; merging them would make one of the two families silently unverifiable.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_receipt_json(value: Any) -> str:
    return hashlib.sha256(receipt_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN` and `Infinity` by default; no producer in this contract writes one."""
    raise InputError(f"a supplied artifact carries the non-finite JSON constant {token}")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """A duplicate member makes a document mean two things; last-wins would pick one silently."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"a supplied artifact carries the duplicate JSON member {key}")
        result[key] = value
    return result


def load_artifact(path: str, label: str) -> dict[str, Any]:
    """Read one supplied artifact. Every failure here is unusable input (exit 2), never a verdict.

    The regular-file check runs BEFORE the read: `open()` on a FIFO blocks until a writer arrives,
    which for a supplied artifact path may be never, so a directory mistake would exit 2 promptly
    while a FIFO mistake hung forever. `Path.stat()` follows a symlink to its target, which is the
    question worth answering -- "is what I would read a regular file".
    """
    candidate = Path(path)
    try:
        mode = candidate.stat().st_mode
    except OSError as exc:
        raise InputError(f"cannot read the {label} artifact {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise InputError(f"the {label} artifact {path} is not a regular file, so it cannot be read")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read the {label} artifact {path}: {exc}") from exc
    try:
        value = json.loads(
            raw.decode("utf-8"), parse_constant=_reject_nonfinite, object_pairs_hook=_reject_duplicates
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"the {label} artifact {path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"the {label} artifact {path} is not a JSON object")
    return value


def require_schema(value: dict[str, Any], key: str, expected: str, label: str, path: str) -> None:
    if value.get(key) != expected:
        raise InputError(f"the {label} artifact {path} is not {expected} ({key}={value.get(key)!r})")


def load_policy(path: str | None) -> dict[str, Any]:
    """Read the checked-in receipt policy for the vocabularies this module refuses to invent."""
    selected = path or str(DEFAULT_POLICY_PATH)
    policy = load_artifact(selected, "runtime assignment receipt policy")
    require_schema(policy, "schema_version", RECEIPT_SCHEMA_VERSION, "runtime assignment receipt policy", selected)
    model_map = policy.get("allowed_exact_model_ids")
    if not isinstance(model_map, dict) or not model_map or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in model_map.items()
    ):
        raise InputError(f"the policy {selected} carries no exact model ID to provider map")
    for field in ("allowed_efforts", "allowed_context_forms", "canonical_receipt_fields"):
        vocabulary = policy.get(field)
        if not isinstance(vocabulary, list) or not vocabulary or not all(isinstance(item, str) for item in vocabulary):
            raise InputError(f"the policy {selected} carries no {field} vocabulary")
    return policy


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve one RFC 6901 pointer, or report UNRESOLVED.

    Re-expressed from `receipt_admission.resolve_json_pointer` for the one thing this module needs
    it for: proving a "verified" readback's recorded value sits at a NAMED position in the bytes. A
    value found somewhere in the bytes proves nothing -- a `highlights` key contains the text `high`.
    """
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        return UNRESOLVED
    current = document
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return UNRESOLVED
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                return UNRESOLVED
            index = int(token)
            if index >= len(current):
                return UNRESOLVED
            current = current[index]
        else:
            return UNRESOLVED
    return current


def parse_body(response_bytes: str) -> Any:
    """Parse transport bytes, or report that they are not structured at all.

    Freeform prose cannot bind a value to a position, so it cannot be a verified readback: an honest
    transport that emits only prose records its readback as `unavailable` instead.
    """
    try:
        return json.loads(response_bytes, object_pairs_hook=_reject_duplicates)
    except (InputError, ValueError):
        return UNPARSEABLE


def request_echo_shapes(assignment: dict[str, Any], requested_value: Any) -> list[Any]:
    """The shapes a holder of the request alone could provably have written.

    Re-expressed from `receipt_admission.request_echo_forms`. Comparison is canonical, so an echo is
    refused on its CONTENT rather than its formatting: whitespace, quoting, and key order normalize
    away before the comparison.
    """
    effort = assignment.get("requested_effort")
    context_form = assignment.get("requested_context_form")
    return [
        requested_value,
        {
            "context_form": context_form,
            "effort": effort,
            "model_id": assignment.get("resolved_model_id"),
            "provider": assignment.get("resolved_provider"),
        },
        {"context_form": context_form, "effort": effort, "model_id": assignment.get("requested_model_id")},
        {"effort": effort},
        {"context_form": context_form},
    ]


def is_request_echo(assignment: dict[str, Any], requested_value: Any, response_bytes: str, parsed: Any) -> bool:
    shapes = request_echo_shapes(assignment, requested_value)
    canonical_forms = {receipt_json(shape) for shape in shapes}
    if response_bytes.strip() in canonical_forms | {str(requested_value)}:
        return True
    if parsed is UNPARSEABLE:
        return False
    return receipt_json(parsed) in canonical_forms or any(parsed == shape for shape in shapes)


def normalize_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def is_tier_token(value: Any) -> bool:
    """True when a value names one of the four semantic tiers rather than a route."""
    return normalize_token(value) in TIERS


def mapped_provider(policy: dict[str, Any], model_id: Any) -> str | None:
    """The provider the versioned policy maps this exact ID to, or None.

    Guards the lookup itself: a document may carry a list or an object where a model ID belongs, and
    `dict.get` on an unhashable key raises `TypeError`, which would leave this module exiting 1 on an
    input it should be answering a verdict about.
    """
    if not isinstance(model_id, str):
        return None
    return policy["allowed_exact_model_ids"].get(model_id)


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class Admission:
    """The accumulating admission evidence. Nothing here decides; `verdict` selects over the lists."""

    def __init__(self, policy_path: str) -> None:
        self.reasons: list[str] = []
        self.injection_gaps: list[str] = []
        self.evaluated: set[str] = set()
        self.missing_fields: list[str] = []
        self.seed_proposal: dict[str, Any] | None = None
        self.evidence: dict[str, Any] = {
            "node": None,
            "policy_path": policy_path,
            "requested_tier": None,
            "requested": {"model_id": None, "effort": None, "context_form": None},
            "resolved": {"provider": None, "model_id": None, "identity_basis": None, "identity_source": None},
            "request_injection_status": None,
            "resolution_state": None,
            # An honestly unavailable effective value is recorded as null with its status, NEVER as
            # the requested value. These two fields are the whole point of the readback clauses.
            "effective": {
                "effort": None,
                "effort_readback_status": None,
                "context_form": None,
                "context_readback_status": None,
            },
            "host_injection": None,
        }

    def refuse(self, reason: str) -> None:
        self.reasons.append(reason)

    def gap(self, reason: str) -> None:
        self.injection_gaps.append(reason)

    def done(self, clause: str) -> None:
        self.evaluated.add(clause)

    def verdict(self) -> str:
        """Exactly one verdict, always, from one ordered selection over one set of lists.

        `seed-proposal` outranks `refuse-dispatch` because the contract names it as the output for an
        uninjectable assignment; every other reason stays listed in the same document. The final
        branch guards this module's own worst failure -- a future early return that drops a clause and
        admits -- and it is a named refusal rather than an `assert`, which `python -O` would strip.
        """
        if self.injection_gaps:
            return VERDICT_SEED
        if self.reasons:
            return VERDICT_REFUSE
        if self.evaluated == ADMISSION_CLAUSES:
            return VERDICT_ADMIT
        self.refuse(
            "not every admission clause was evaluated (missing "
            + ", ".join(sorted(ADMISSION_CLAUSES - self.evaluated))
            + "), and an unevaluated clause is refused rather than assumed satisfied"
        )
        return VERDICT_REFUSE


def field(assignment: dict[str, Any], name: str) -> Any:
    """Read one assignment field, or MISSING. `None` is a value; absence is not."""
    return assignment.get(name, MISSING)


def clause_completeness(admission: Admission, assignment: dict[str, Any], policy: dict[str, Any]) -> None:
    """An INCOMPLETE assignment stops before dispatch, and the reason names every absent field."""
    admission.done("completeness")
    expected = [name for name in policy["canonical_receipt_fields"] if name != "schema_version"]
    admission.missing_fields = [name for name in expected if assignment.get(name, MISSING) is MISSING]
    if admission.missing_fields:
        admission.refuse(
            "the assignment is incomplete and an incomplete assignment stops before dispatch; "
            "missing: " + ", ".join(admission.missing_fields)
        )


def clause_resolution_state(admission: Admission, assignment: dict[str, Any]) -> None:
    """`resolution_state` must be exactly `resolved`; every other state is a request, not proof."""
    admission.done("resolution_state")
    state = field(assignment, "resolution_state")
    if state is MISSING:
        return
    admission.evidence["resolution_state"] = state
    if state == RESOLUTION_RESOLVED:
        return
    named = {
        RESOLUTION_INHERITED: (
            f"resolution_state is {RESOLUTION_INHERITED!r}: an inherited model selection is recorded, "
            "never proof, so this assignment stops before dispatch and therefore before spawn"
        ),
        RESOLUTION_UNRESOLVED: (
            f"resolution_state is {RESOLUTION_UNRESOLVED!r}: no exact route was resolved, so this "
            "assignment stops before dispatch and therefore before spawn"
        ),
        RESOLUTION_REQUESTED: (
            f"resolution_state is {RESOLUTION_REQUESTED!r}: a requested model selection is recorded, "
            "never proof, so this assignment stops before dispatch and therefore before spawn"
        ),
    }
    admission.refuse(
        named.get(
            state,
            f"resolution_state is {state!r} and must equal {RESOLUTION_RESOLVED!r}; anything else "
            "stops before dispatch and therefore before spawn",
        )
    )


def clause_tier_separation(
    admission: Admission, request: dict[str, Any], assignment: dict[str, Any], policy: dict[str, Any]
) -> None:
    """The requested TIER and the resolved provider/model are separate facts, in both directions."""
    admission.done("tier_separation")
    model_map = policy["allowed_exact_model_ids"]
    tier = request.get("requested_tier", MISSING)
    admission.evidence["requested_tier"] = None if tier is MISSING else tier
    if tier is MISSING or tier is None:
        admission.refuse(
            "the admission request records no requested_tier, so the semantic tier decision and the "
            f"resolved exact identity are not kept as separate facts; one of {list(TIERS)} is required"
        )
    elif not isinstance(tier, str) or tier in model_map or not is_tier_token(tier):
        # Direction A: the tier field carries a route. An exact model ID is the ANSWER to routing,
        # not the tier question, and a document that puts it here has merged the two facts.
        admission.refuse(
            f"requested_tier is {tier!r}, which is not one of the semantic tiers {list(TIERS)}; a "
            "model ID or route in the tier field conflates the requested tier with the resolved "
            "provider/model"
        )
    # Direction B: an identity field carries a tier. This refusal is deliberately its own reason
    # rather than leaving the generic mapping refusal to speak: "capable-volume is not an allowed
    # exact model ID" does not tell the human that a tier was pasted into a route field.
    for name in ("resolved_model_id", "resolved_provider"):
        value = field(assignment, name)
        if value is not MISSING and is_tier_token(value):
            admission.refuse(
                f"{name} is {value!r}, which is a semantic tier and not a resolved route; the "
                "requested tier and the resolved provider/model are separate facts"
            )


def clause_request_injection(admission: Admission, assignment: dict[str, Any]) -> None:
    """Exact model/effort/context request injection is mandatory and immutable, and it is EVIDENCE."""
    admission.done("request_injection")
    status = field(assignment, "request_injection_status")
    evidence = field(assignment, "request_injection_evidence")
    if status is not MISSING:
        admission.evidence["request_injection_status"] = status
        if status != STATUS_VERIFIED:
            admission.refuse(
                f"request_injection_status is {status!r} and must equal {STATUS_VERIFIED!r}: exact "
                "model and effort request injection is mandatory and immutable"
            )
    if evidence is MISSING:
        return
    if not isinstance(evidence, dict):
        admission.refuse("request_injection_evidence is not an object, so no injection is evidenced")
        return
    digest = evidence.get("request_bytes_sha256")
    if not is_sha256(digest):
        admission.refuse(
            "request_injection_evidence carries no lowercase SHA-256 request_bytes_sha256, so the "
            "exact requested model, effort, and context form are not bound by immutable evidence"
        )
        return
    expected = {
        "context_form": assignment.get("requested_context_form"),
        "effort": assignment.get("requested_effort"),
        "model_id": assignment.get("requested_model_id"),
    }
    if digest != sha256_receipt_json(expected):
        admission.refuse(
            "request_injection_evidence does not bind the requested model, effort, and context "
            "bytes, so the exact request that was sent is not evidenced"
        )


def clause_request_immutability(admission: Admission, assignment: dict[str, Any], policy: dict[str, Any]) -> None:
    """The injected exact model is immutable, and the requested effort/context are in vocabulary."""
    admission.done("request_immutability")
    requested_model = field(assignment, "requested_model_id")
    resolved_model = field(assignment, "resolved_model_id")
    if requested_model is not MISSING:
        admission.evidence["requested"]["model_id"] = requested_model
    if resolved_model is not MISSING:
        admission.evidence["resolved"]["model_id"] = resolved_model
    if requested_model is not MISSING and resolved_model is not MISSING and requested_model != resolved_model:
        admission.refuse(
            f"resolved_model_id {resolved_model!r} is not the requested {requested_model!r}: exact "
            "model request injection is immutable, so a pre-spawn substitution stops before dispatch"
        )
    for axis, (requested_field, _observed, vocabulary_key, _divergence) in EFFECTIVE_AXES.items():
        value = field(assignment, requested_field)
        if value is MISSING:
            continue
        admission.evidence["requested"]["effort" if axis == "effort" else "context_form"] = value
        if value not in policy[vocabulary_key]:
            admission.refuse(
                f"{requested_field} is {value!r}, which is not in the policy {vocabulary_key} "
                "vocabulary, so no exact request could have been injected"
            )


def clause_model_identity(admission: Admission, assignment: dict[str, Any], policy: dict[str, Any]) -> None:
    """`resolved_provider`/`resolved_model_id` require verified model identity, on a named basis."""
    admission.done("model_identity")
    model_map = policy["allowed_exact_model_ids"]
    basis = field(assignment, "model_identity_basis")
    status = field(assignment, "model_readback_status")
    provider = field(assignment, "resolved_provider")
    model_id = field(assignment, "resolved_model_id")
    evidence = field(assignment, "model_readback_evidence")
    if basis is not MISSING:
        admission.evidence["resolved"]["identity_basis"] = basis
    if provider is not MISSING:
        admission.evidence["resolved"]["provider"] = provider
    if status is not MISSING and status != STATUS_VERIFIED:
        admission.refuse(
            f"model_readback_status is {status!r} and must equal {STATUS_VERIFIED!r}: resolved_provider "
            "and resolved_model_id require verified model identity"
        )
    if model_id is not MISSING:
        mapped = mapped_provider(policy, model_id)
        if mapped is None:
            admission.refuse(
                f"resolved_model_id {model_id!r} is not an exact model ID the policy maps to a "
                "provider, so its identity cannot be verified against the versioned policy"
            )
        elif provider is not MISSING and provider != mapped:
            admission.refuse(
                f"resolved_provider {provider!r} is not the policy-mapped provider {mapped!r} for "
                f"{model_id!r}, so the resolved route is not one identity"
            )
    if basis is MISSING:
        return
    if basis == BASIS_READBACK:
        _independent_identity(admission, assignment, evidence)
        return
    if basis == BASIS_MAPPING:
        _mapping_identity(admission, assignment, evidence, policy)
        return
    admission.refuse(
        f"model_identity_basis is {basis!r}, which is neither {BASIS_READBACK!r} nor {BASIS_MAPPING!r}, "
        "so the basis for the resolved identity is unnamed"
    )


def _independent_identity(admission: Admission, assignment: dict[str, Any], evidence: Any) -> None:
    """Independent observation: a NAMED admissible source that binds the receipt's resolved pair."""
    if not isinstance(evidence, dict):
        admission.refuse("model_readback_evidence is not an object, so no independent readback is evidenced")
        return
    source = evidence.get("observed_identity_source")
    admission.evidence["resolved"]["identity_source"] = source
    if source == IDENTITY_SOURCE_GATEWAY_BODY:
        # Refused by name rather than graded: on a gateway route the response body reports the
        # caller's own request string, so a caller-chosen alias comes back as identity.
        admission.refuse(
            "model_readback_evidence names the gateway response body as its identity source; that "
            "body echoes the caller's requested model string, so record the gateway attribution log "
            "or an unavailable readback instead"
        )
    elif source not in ADMISSIBLE_IDENTITY_SOURCES:
        admission.refuse(
            f"model_readback_evidence observed_identity_source is {source!r}, not one of "
            f"{list(ADMISSIBLE_IDENTITY_SOURCES)}, so the observation names no admissible provenance"
        )
    if evidence.get("status") != STATUS_VERIFIED:
        admission.refuse(
            f"model_readback_evidence status is {evidence.get('status')!r}: an independent identity "
            f"readback must be {STATUS_VERIFIED!r}"
        )
    for evidence_field, receipt_field in (("observed_provider", "resolved_provider"), ("observed_model_id", "resolved_model_id")):
        observed = evidence.get(evidence_field)
        if not is_nonempty_string(observed):
            admission.refuse(
                f"model_readback_evidence {evidence_field} is not a non-empty string, so nothing was "
                "independently observed"
            )
        elif observed != assignment.get(receipt_field):
            admission.refuse(
                f"model_readback_evidence {evidence_field} {observed!r} does not equal the receipt's "
                f"{receipt_field} {assignment.get(receipt_field)!r}, so the observation is about a "
                "different route"
            )


def _mapping_identity(
    admission: Admission, assignment: dict[str, Any], evidence: Any, policy: dict[str, Any]
) -> None:
    """The one carve-out, and its exact price.

    An independently observed provider/model source may be UNAVAILABLE only for an unambiguous
    exact-ID mapping backed by immutable request/model evidence. Both halves are load-bearing: the
    mapping must be unambiguous under the versioned policy, and the immutable request evidence must
    be verified. Without the second half the carve-out would let any unobserved route in.
    """
    model_id = assignment.get("resolved_model_id")
    if mapped_provider(policy, model_id) is None:
        admission.refuse(
            f"model_identity_basis is {BASIS_MAPPING!r} but resolved_model_id {model_id!r} has no "
            "exact mapping in the versioned policy, so the mapping is not unambiguous"
        )
    if assignment.get("request_injection_status") != STATUS_VERIFIED:
        admission.refuse(
            f"model_identity_basis is {BASIS_MAPPING!r} without verified request injection: an "
            "unavailable independent observation is admissible only for an unambiguous exact-ID "
            "mapping backed by immutable request and model evidence"
        )
    if not isinstance(evidence, dict):
        admission.refuse("model_readback_evidence is not an object, so the exact-ID mapping is not evidenced")
        return
    admission.evidence["resolved"]["identity_source"] = evidence.get("source_kind")
    reference = policy.get("model_mapping_reference")
    if evidence.get("reference") != reference:
        admission.refuse(
            f"model_readback_evidence reference is {evidence.get('reference')!r}, not the policy "
            f"mapping reference {reference!r}, so the mapping is not the versioned one"
        )
    if evidence.get("mapped_model_id") != model_id or evidence.get("mapped_provider") != assignment.get(
        "resolved_provider"
    ):
        admission.refuse(
            "model_readback_evidence does not bind the mapped provider and model to the receipt's "
            "resolved pair, so the mapping evidence is about a different route"
        )
    if not is_sha256(evidence.get("assignment_binding_sha256")):
        admission.refuse(
            "model_readback_evidence carries no lowercase SHA-256 assignment_binding_sha256, so the "
            "mapping evidence is not bound to this assignment"
        )
        return
    expected = {
        "context_form": assignment.get("requested_context_form"),
        "effort": assignment.get("requested_effort"),
        "model_id": assignment.get("resolved_model_id"),
        "provider": assignment.get("resolved_provider"),
    }
    if evidence["assignment_binding_sha256"] != sha256_receipt_json(expected):
        admission.refuse(
            "model_readback_evidence assignment_binding_sha256 does not bind this assignment, so the "
            "mapping evidence was captured for a different one"
        )


def clause_effective_readback(
    admission: Admission, axis: str, assignment: dict[str, Any], policy: dict[str, Any]
) -> None:
    """Effective effort/context readback may be honestly unavailable; requested values never become it.

    Two shapes are refused, and they are the same lie wearing different masks: a `verified` readback
    whose bytes are a request echo, and an `unavailable` readback that nonetheless records an observed
    value. An honest `unavailable` is ADMITTED and is recorded as unavailable -- never as the
    requested value.
    """
    admission.done(f"{axis}_readback")
    requested_field, observed_key, vocabulary_key, divergence_field = EFFECTIVE_AXES[axis]
    status_field = f"{axis}_readback_status"
    effective_key = "effort" if axis == "effort" else "context_form"
    status = field(assignment, status_field)
    evidence = field(assignment, f"{axis}_readback_evidence")
    divergence = field(assignment, divergence_field)
    if status is MISSING:
        return
    admission.evidence["effective"][f"{axis}_readback_status"] = status
    if status not in (STATUS_VERIFIED, STATUS_UNAVAILABLE):
        admission.refuse(
            f"{status_field} is {status!r} and must be {STATUS_VERIFIED!r} or {STATUS_UNAVAILABLE!r}"
        )
        return
    if not isinstance(evidence, dict):
        admission.refuse(f"{axis}_readback_evidence is not an object, so the readback is not evidenced")
        return

    if status == STATUS_UNAVAILABLE:
        leaked = sorted(key for key in (observed_key, "response_bytes", "observed_value_pointer") if key in evidence)
        if leaked:
            admission.refuse(
                f"{status_field} is {STATUS_UNAVAILABLE!r} yet {axis}_readback_evidence carries "
                + ", ".join(leaked)
                + f": an unavailable effective {axis} is its own fact and never carries a value"
            )
        if divergence is not MISSING and divergence != DIVERGENCE_UNAVAILABLE:
            admission.refuse(
                f"{divergence_field} is {divergence!r} although the {axis} readback is "
                f"{STATUS_UNAVAILABLE!r}, so a divergence is declared that was never observed"
            )
        # The effective value stays null. This is the recording the contract demands: honestly
        # unavailable, never the requested value.
        return

    observed = evidence.get(observed_key, MISSING)
    response_bytes = evidence.get("response_bytes", MISSING)
    pointer = evidence.get("observed_value_pointer", MISSING)
    if observed is MISSING or response_bytes is MISSING or pointer is MISSING:
        admission.refuse(
            f"{status_field} is {STATUS_VERIFIED!r} but {axis}_readback_evidence carries no "
            f"{observed_key}, response_bytes, and observed_value_pointer together: a verified "
            f"readback that names no observation is the requested {axis}, not a readback of it"
        )
        return
    if not is_nonempty_string(response_bytes):
        admission.refuse(f"{axis}_readback_evidence response_bytes is not a non-empty string")
        return
    if not is_sha256(evidence.get("readback_bytes_sha256")) or evidence["readback_bytes_sha256"] != sha256_text(
        response_bytes
    ):
        admission.refuse(
            f"{axis}_readback_evidence readback_bytes_sha256 does not bind the transport response "
            "bytes, so the observation is not bound to what the transport said"
        )
    parsed = parse_body(response_bytes)
    if is_request_echo(assignment, assignment.get(requested_field), response_bytes, parsed):
        # THE conflation the contract forbids, and the most dangerous input in this space: the
        # receipt is structurally complete and every status says verified.
        admission.refuse(
            f"{axis}_readback_evidence response_bytes are a request echo, not a transport readback: "
            "requested values never become readback"
        )
        return
    if parsed is UNPARSEABLE:
        admission.refuse(
            f"{axis}_readback_evidence response_bytes do not parse as JSON, so freeform transport "
            f"text cannot bind an effective {axis}; record it as {STATUS_UNAVAILABLE!r} instead"
        )
        return
    if not isinstance(pointer, str):
        admission.refuse(f"{axis}_readback_evidence observed_value_pointer is not a JSON pointer string")
        return
    located = resolve_json_pointer(parsed, pointer)
    if located is UNRESOLVED or not isinstance(located, str) or located != observed:
        admission.refuse(
            f"{axis}_readback_evidence {observed_key} is not the value the transport reported at "
            "observed_value_pointer, so the recorded observation is unbound"
        )
        return
    if observed not in policy[vocabulary_key]:
        admission.refuse(
            f"{axis}_readback_evidence {observed_key} is {observed!r}, outside the policy "
            f"{vocabulary_key} vocabulary; an out-of-vocabulary transport report is recorded as "
            f"{STATUS_UNAVAILABLE!r}, never as verified"
        )
        return
    expected_divergence = (
        MATCHES_REQUESTED if observed == assignment.get(requested_field) else DIVERGES_FROM_REQUESTED
    )
    if divergence is not MISSING and divergence != expected_divergence:
        admission.refuse(
            f"{divergence_field} is {divergence!r} but the observed {axis} {observed!r} against the "
            f"requested {assignment.get(requested_field)!r} is {expected_divergence!r}"
        )
        return
    admission.evidence["effective"][effective_key] = observed


def clause_host_injection(admission: Admission, request: dict[str, Any]) -> None:
    """The selected host must inject BOTH the exact model and the exact effort, or this is a Seed."""
    admission.done("host_injection")
    declaration = request.get("host_injection", MISSING)
    if declaration is MISSING or not isinstance(declaration, dict):
        admission.refuse(
            "the admission request declares no host_injection capability object, so it is not proven "
            "that the selected host or launcher can inject the exact requested model and effort"
        )
        return
    unexpected = sorted(set(declaration) - HOST_INJECTION_FIELDS)
    missing = sorted(HOST_INJECTION_FIELDS - set(declaration))
    if missing or unexpected:
        admission.refuse(
            "host_injection is not the closed capability declaration "
            + f"{sorted(HOST_INJECTION_FIELDS)}"
            + (f"; missing {missing}" if missing else "")
            + (f"; unexpected {unexpected}" if unexpected else "")
        )
        return
    admission.evidence["host_injection"] = {
        "host": declaration["host"],
        "surface": declaration["surface"],
        "injects_model": declaration["injects_model"],
        "injects_effort": declaration["injects_effort"],
    }
    for name, subject in (("injects_model", "the exact model"), ("injects_effort", "the exact effort")):
        value = declaration[name]
        if not isinstance(value, bool):
            # A string "false" reads as truthy, which would turn an uninjectable host into an
            # admitted dispatch. A capability that is not STATED as a boolean is not stated.
            admission.refuse(
                f"host_injection {name} is {value!r} and not a boolean, so whether the host injects "
                f"{subject} cannot be established"
            )
        elif not value:
            admission.gap(
                f"the selected host {declaration['host']!r} on surface {declaration['surface']!r} "
                f"cannot inject {subject}; prompt prose does not enforce a model or effort"
            )


def seed_proposal_for(admission: Admission, request: dict[str, Any]) -> dict[str, Any]:
    """The repository's typed `SeedProposal`, and the ONLY output shape for an uninjectable host."""
    node = request.get("node")
    requested = admission.evidence["requested"]
    proposal = {
        "title": "Injectable exact model and effort for "
        + (str(node) if is_nonempty_string(node) else "one unnamed workflow node"),
        "summary": (
            "The conductor certified a RuntimeAssignment this host cannot dispatch: "
            + "; ".join(admission.injection_gaps)
            + ". The contract's output for an uninjectable assignment is one SeedProposal, not a "
            "dispatch, so no spawn followed."
        ),
        "acceptance_criteria": [
            "The selected host or launcher injects the exact requested model ID at the call site.",
            "The selected host or launcher injects the exact requested effort at the call site.",
            "Immutable request-injection evidence binds the exact model, effort, and context form.",
            "Re-running this admission over the same assignment returns " + VERDICT_ADMIT + ".",
        ],
        "priority": "high",
        "blocking": True,
        "scope": [str(node) if is_nonempty_string(node) else "unnamed-node"],
        "evidence": list(admission.injection_gaps) + list(admission.reasons),
        "dependencies": [],
        "recommended_owner": "conductor",
    }
    if tuple(proposal) != SEED_PROPOSAL_FIELDS:
        raise InputError("the constructed SeedProposal does not carry the typed field order")
    proposal_requested = {key: requested[key] for key in ("model_id", "effort", "context_form")}
    proposal["evidence"].append("requested route: " + receipt_json(proposal_requested))
    return proposal


def admit_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Derive exactly one pre-spawn admission verdict for one RuntimeAssignment."""
    policy_path = args.policy or str(DEFAULT_POLICY_PATH)
    policy = load_policy(args.policy)
    request = load_artifact(args.request, "admission request")
    require_schema(request, "schema", REQUEST_SCHEMA, "admission request", args.request)
    assignment = request.get("assignment")
    if not isinstance(assignment, dict):
        raise InputError(
            f"the admission request artifact {args.request} carries no assignment object, so no "
            "RuntimeAssignment was supplied to admit"
        )
    require_schema(assignment, "schema_version", RECEIPT_SCHEMA_VERSION, "embedded assignment", args.request)

    admission = Admission(policy_path)
    admission.evidence["node"] = request.get("node")
    clause_completeness(admission, assignment, policy)
    clause_resolution_state(admission, assignment)
    clause_tier_separation(admission, request, assignment, policy)
    clause_request_injection(admission, assignment)
    clause_request_immutability(admission, assignment, policy)
    clause_model_identity(admission, assignment, policy)
    clause_effective_readback(admission, "effort", assignment, policy)
    clause_effective_readback(admission, "context", assignment, policy)
    clause_host_injection(admission, request)

    verdict = admission.verdict()
    if verdict == VERDICT_SEED:
        admission.seed_proposal = seed_proposal_for(admission, request)
    result = {
        "schema": ADMISSION_SCHEMA,
        "command": "admit",
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": ADMISSION_CONSEQUENCE[verdict],
        "may_spawn": verdict == VERDICT_ADMIT,
        "reasons": admission.reasons,
        "injection_gaps": admission.injection_gaps,
        "seed_proposal": admission.seed_proposal,
        "evidence": admission.evidence,
    }
    return result, EXIT_OK


class Classification:
    """The accumulating substitution evidence for one receipt. `verdict` selects over the lists."""

    def __init__(self, policy_path: str) -> None:
        self.unexplained: list[str] = []
        self.explained: list[str] = []
        self.axes: dict[str, dict[str, Any]] = {}
        self.evidence: dict[str, Any] = {"node": None, "policy_path": policy_path}

    def record(self, axis: str, **fields: Any) -> None:
        self.axes[axis] = {"axis": axis, **fields}

    def block(self, axis: str, reason: str) -> None:
        self.unexplained.append(reason)
        self.axes[axis]["disposition"] = "unexplained"
        self.axes[axis]["reason"] = reason

    def explain(self, axis: str, authorization: dict[str, Any]) -> None:
        self.explained.append(
            f"the {axis} substitution is authorized by {authorization['authorized_by']!r} in "
            f"{authorization['approved_in']!r}"
        )
        self.axes[axis]["disposition"] = "explained"
        self.axes[axis]["authorization"] = {
            "authorized_by": authorization["authorized_by"],
            "approved_in": authorization["approved_in"],
        }

    def verdict(self) -> str:
        """Exactly one verdict, always, and the fail-closed sink absorbs everything unprovable."""
        if self.unexplained:
            return VERDICT_UNEXPLAINED
        if self.explained:
            return VERDICT_EXPLAINED
        if set(self.axes) == CLASSIFICATION_AXES:
            return VERDICT_EXACT
        self.unexplained.append(
            "not every substitution axis was classified (missing "
            + ", ".join(sorted(CLASSIFICATION_AXES - set(self.axes)))
            + "), and an unclassified axis is unexplained rather than assumed matching"
        )
        return VERDICT_UNEXPLAINED


def matching_authorization(
    classification: Classification, axis: str, from_value: Any, to_value: Any, to_provider: Any, entries: list[Any]
) -> dict[str, Any] | None:
    """The one envelope entry that authorizes this exact difference, or None with a named reason.

    Exactly one entry must match. Two entries authorizing the same difference make the envelope
    ambiguous about which authority applies, and an ambiguous authorization is not a named one.
    """
    matched: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != AUTHORIZATION_FIELDS:
            classification.block(
                axis,
                "an authorized_substitutions entry is not the closed envelope shape "
                f"{sorted(AUTHORIZATION_FIELDS)}, so no substitution is proven authorized",
            )
            return None
        if entry["axis"] != axis or entry["from"] != from_value or entry["to"] != to_value:
            continue
        if axis == "model" and entry["to_provider"] != to_provider:
            continue
        matched.append(entry)
    if not matched:
        classification.block(
            axis,
            f"the served {axis} {to_value!r} differs from the requested {from_value!r} and no entry "
            "in the approved envelope authorizes that substitution, so it is UNEXPLAINED",
        )
        return None
    if len(matched) > 1:
        classification.block(
            axis,
            f"{len(matched)} envelope entries authorize the same {axis} substitution, so which "
            "authority applies is ambiguous and no single authorization is named",
        )
        return None
    entry = matched[0]
    if not is_nonempty_string(entry["authorized_by"]) or not is_nonempty_string(entry["approved_in"]):
        classification.block(
            axis,
            f"the envelope entry for the {axis} substitution names no authorization "
            f"(authorized_by={entry['authorized_by']!r}, approved_in={entry['approved_in']!r}), and "
            "an unnamed authority does not explain a substitution",
        )
        return None
    return entry


def classify_identity(
    classification: Classification,
    requested: dict[str, Any],
    served: dict[str, Any],
    entries: list[Any],
    policy: dict[str, Any],
) -> None:
    """Was the requested route the served route? Anything unprovable lands in UNEXPLAINED."""
    axis = "model"
    status = served.get("identity_status")
    served_model = served.get("model_id", MISSING)
    served_provider = served.get("provider", MISSING)
    classification.record(
        axis,
        requested=requested.get("model_id"),
        requested_provider=mapped_provider(policy, requested.get("model_id")),
        served=None if served_model is MISSING else served_model,
        served_provider=None if served_provider is MISSING else served_provider,
        readback_status=status,
        identity_source=served.get("identity_source"),
        identity_basis=served.get("identity_basis"),
        disposition="matches",
    )
    if status == STATUS_UNAVAILABLE:
        # FIRST the same internal-honesty rule `classify_effective` applies to its own axis, and it
        # is what closes the mask this axis is worth the most to hide a substitution in: a gateway
        # falls back silently, the harness records the unverified fallback hint as `model_id` beside
        # an honest `unavailable`, and the carve-out below would then call that route an exact match
        # of a model it never served.
        #
        # The rule is NOT "carry nothing", because `_mapping_identity` REQUIRES the admitted
        # assignment's resolved pair to be populated and to equal the mapping's own output; a classify
        # side that demanded null here would contradict the admit side of the same carve-out. The rule
        # is that an unobserved record may state exactly ONE route -- the one the exact-ID mapping
        # derives from the request -- so a field may be absent, null, or the mapping's own value, and
        # anything else is an unverified route wearing an observation's clothes. The provider is
        # compared only when the requested ID is mapped at all; when it is not, the unambiguity
        # refusal below is the reason a human needs.
        mapped = mapped_provider(policy, requested.get("model_id"))
        masked: list[str] = []
        if served_model is not MISSING and served_model is not None and served_model != requested.get("model_id"):
            masked.append(f"model_id {served_model!r} where the request was {requested.get('model_id')!r}")
        if (
            mapped is not None
            and served_provider is not MISSING
            and served_provider is not None
            and served_provider != mapped
        ):
            masked.append(f"provider {served_provider!r} where the policy maps that model to {mapped!r}")
        if masked:
            classification.block(
                axis,
                f"the served route identity is {STATUS_UNAVAILABLE!r}, so the only route this record "
                "may state is the one the exact-ID mapping derives, yet it carries "
                + "; ".join(masked)
                + ": an unavailable readback never carries a value it did not derive, and an "
                "unverified fallback recorded as the served route is the conflation this contract "
                "forbids on the axis that decides which model actually ran",
            )
            return
        # The same carve-out `admit` applies, and for the same reason: an unobserved route is
        # admissible only when the exact ID maps unambiguously AND immutable request evidence backs it.
        if served.get("identity_basis") != BASIS_MAPPING:
            classification.block(
                axis,
                "the served route identity is unavailable and no unambiguous exact-ID mapping is "
                "claimed, so what actually served cannot be proven and is UNEXPLAINED",
            )
            return
        if mapped is None:
            classification.block(
                axis,
                f"the served route identity is unavailable and the requested {requested.get('model_id')!r} "
                "has no exact mapping in the versioned policy, so the mapping is not unambiguous",
            )
            return
        if served.get("request_injection_status") != STATUS_VERIFIED:
            classification.block(
                axis,
                "the served route identity is unavailable and request injection is not verified, so "
                "the exact-ID mapping is not backed by immutable request evidence",
            )
            return
        classification.axes[axis]["disposition"] = "matches-by-exact-id-mapping"
        return
    if status != STATUS_VERIFIED:
        classification.block(
            axis,
            f"the served identity_status is {status!r}, neither {STATUS_VERIFIED!r} nor "
            f"{STATUS_UNAVAILABLE!r}, so what served is unestablished and therefore UNEXPLAINED",
        )
        return
    source = served.get("identity_source")
    if source == IDENTITY_SOURCE_GATEWAY_BODY:
        classification.block(
            axis,
            "the served identity comes from the gateway response body, which echoes the caller's own "
            "requested model string, so it establishes nothing about what served",
        )
        return
    if source not in ADMISSIBLE_IDENTITY_SOURCES:
        classification.block(
            axis,
            f"the served identity_source is {source!r}, not one of {list(ADMISSIBLE_IDENTITY_SOURCES)}, "
            "so the observation names no admissible provenance",
        )
        return
    if is_tier_token(served_model) or is_tier_token(served_provider):
        classification.block(
            axis,
            f"the served route is recorded as {served_provider!r}/{served_model!r}, which names a "
            "semantic tier and not a served model identity",
        )
        return
    if not is_nonempty_string(served_model) or not is_nonempty_string(served_provider):
        classification.block(
            axis,
            "the served provider and model are not both non-empty strings, so no served route "
            "identity was recorded at all",
        )
        return
    # The provider cross-check runs on BOTH paths, before the requested/served comparison splits
    # them. Running it only where the model matched left the substituted path unchecked, so an
    # envelope entry could predeclare `to_provider` as a provider the versioned policy does not map
    # that model to and carry a jointly impossible route into `explained-substitution`. An
    # authorization names an authority for a difference; it cannot make an impossible route possible.
    expected_provider = mapped_provider(policy, served_model)
    if expected_provider is None:
        # An out-of-vocabulary served ID is UNEXPLAINED even when it equals the request. Equality
        # then proves only that the record repeats itself: nothing constrains the served provider,
        # so `evil-corp` would pass, and identity cannot be established against the versioned
        # policy at all. `admit` refuses this exact ID before spawn for the same reason, and the two
        # halves of one contract may not disagree about whether a route is knowable.
        classification.block(
            axis,
            f"the served model {served_model!r} is not an exact model ID the versioned policy maps "
            f"to a provider, so the served provider {served_provider!r} is checked against nothing "
            "and what served cannot be established; an out-of-vocabulary route is UNEXPLAINED, "
            "never a clean exact match",
        )
        return
    if served_provider != expected_provider:
        matched = served_model == requested.get("model_id")
        classification.block(
            axis,
            f"the served model {served_model!r} "
            + ("matches the request" if matched else f"substitutes the requested {requested.get('model_id')!r}")
            + f" but was served by {served_provider!r} rather than the policy-mapped "
            f"{expected_provider!r}, which is a route substitution"
            + (
                ""
                if matched
                else "; no envelope entry can authorize a provider the versioned policy does not "
                "map this model to, because that route is jointly impossible"
            ),
        )
        return
    if served_model == requested.get("model_id"):
        return
    authorization = matching_authorization(
        classification, axis, requested.get("model_id"), served_model, served_provider, entries
    )
    if authorization is not None:
        classification.explain(axis, authorization)


def classify_effective(
    classification: Classification,
    axis: str,
    requested: dict[str, Any],
    served: dict[str, Any],
    entries: list[Any],
    policy: dict[str, Any],
) -> None:
    """An honestly unavailable effective value is not a substitution; a masked one is."""
    requested_key = "effort" if axis == "effort" else "context_form"
    _requested_field, _observed, vocabulary_key, _divergence = EFFECTIVE_AXES[axis]
    status = served.get(f"{axis}_readback_status")
    value = served.get(requested_key, MISSING)
    requested_value = requested.get(requested_key)
    classification.record(
        axis,
        requested=requested_value,
        served=None if value is MISSING else value,
        readback_status=status,
        disposition="matches",
    )
    if status == STATUS_UNAVAILABLE:
        if value is not MISSING and value is not None:
            classification.block(
                axis,
                f"the served record says the effective {axis} readback is {STATUS_UNAVAILABLE!r} yet "
                f"carries {value!r}: an unavailable readback never carries a value, and a requested "
                "value presented as one is the conflation this contract forbids",
            )
            return
        classification.axes[axis]["disposition"] = "unavailable"
        classification.axes[axis]["served"] = None
        return
    if status != STATUS_VERIFIED:
        classification.block(
            axis,
            f"the served {axis}_readback_status is {status!r}, neither {STATUS_VERIFIED!r} nor "
            f"{STATUS_UNAVAILABLE!r}, so the effective {axis} is unestablished and UNEXPLAINED",
        )
        return
    if value is MISSING or value not in policy[vocabulary_key]:
        classification.block(
            axis,
            f"the served record claims a {STATUS_VERIFIED!r} {axis} readback of "
            f"{None if value is MISSING else value!r}, which is outside the policy {vocabulary_key} "
            f"vocabulary; an out-of-vocabulary report is recorded as {STATUS_UNAVAILABLE!r}",
        )
        return
    if value == requested_value:
        return
    authorization = matching_authorization(classification, axis, requested_value, value, None, entries)
    if authorization is not None:
        classification.explain(axis, authorization)


def classify_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Classify one served record against its request: exact, explained, or unexplained."""
    policy_path = args.policy or str(DEFAULT_POLICY_PATH)
    policy = load_policy(args.policy)
    record = load_artifact(args.served, "served record")
    require_schema(record, "schema", SERVED_SCHEMA, "served record", args.served)
    requested = record.get("requested")
    served = record.get("served")
    if not isinstance(requested, dict) or not isinstance(served, dict):
        raise InputError(
            f"the served record {args.served} does not carry both a requested and a served object, so "
            "there is nothing to compare"
        )
    entries = record.get("authorized_substitutions", [])
    if not isinstance(entries, list):
        raise InputError(
            f"the served record {args.served} carries an authorized_substitutions value that is not a "
            "list, so the approved envelope cannot be read"
        )

    classification = Classification(policy_path)
    classification.evidence["node"] = record.get("node")
    classify_identity(classification, requested, served, entries, policy)
    classify_effective(classification, "effort", requested, served, entries, policy)
    classify_effective(classification, "context", requested, served, entries, policy)

    verdict = classification.verdict()
    result = {
        "schema": CLASSIFICATION_SCHEMA,
        "command": "classify",
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CLASSIFICATION_CONSEQUENCE[verdict],
        "blocks_wave_completion": verdict == VERDICT_UNEXPLAINED,
        "reasons": classification.unexplained,
        "explanations": classification.explained,
        "axes": [classification.axes[axis] for axis in sorted(classification.axes)],
        "evidence": classification.evidence,
    }
    return result, EXIT_OK


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process has ALREADY reported as failed.

    Re-expressed from `gate_receipt.abandon_broken_stream`. Catching the failed write is not enough:
    the bytes stay PENDING in the stream's buffer and CPython flushes `sys.stdout`/`sys.stderr` once
    more while finalizing, and that second failure replaces the process exit code with 120 -- outside
    this module's closed exit set entirely. Dropping the module attribute is how CPython itself
    represents a stream this process does not have (`2>&-` starts the interpreter with
    `sys.stderr is None`), and it loses no byte that the failed write had not already lost. The
    identity check is load-bearing because `main` is importable: only the stream that actually failed
    may be dropped, never a caller's replacement.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def guarded_sink(name: str, stream: object) -> Callable[[str], None]:
    """Wrap one already-settled display stream so a failed write costs the channel, never the code.

    The first failure retires the channel -- silently, because there is by definition nowhere left to
    report it -- and every later line is a no-op. Flushing is not optional: it is what makes a broken
    channel announce itself HERE, where the failure can still be contained, instead of during
    finalization where it becomes exit 120.
    """
    if stream is None:  # `2>&-` / `1>&-`: this process was handed no such stream
        return lambda line: None
    write = getattr(stream, "write", None)
    if not callable(write):
        return lambda line: None
    flush = getattr(stream, "flush", None)
    live = [True]

    def emit(line: str) -> None:
        if not live[0]:
            return
        try:
            write(line)
            if callable(flush):
                flush()
        except (OSError, ValueError):  # EPIPE/ENOSPC, or a stream closed underneath us
            live[0] = False
            abandon_broken_stream(name, stream)

    return emit


def advisory_stderr() -> Callable[[str], None]:
    """Settle this module's display-only sink for diagnostics and argparse's own usage lines.

    Re-expressed from `gate_receipt.advisory_stderr`, which owns this rule; the two are deliberately
    separate copies rather than an import across a skill boundary. Every line through here is display
    only -- the classified exit code and the presence or absence of the one result document on stdout
    are the evidence -- so a stream that cannot accept a line must cost the channel and nothing else.
    Two hostile shapes are ordinary: `2>&-` leaves `sys.stderr is None`, so an unguarded write raises
    `AttributeError` and replaces exit 2 with exit 1; a reader that has gone away makes every write
    `EPIPE` and replaces exit 2 with exit 120.
    """
    return guarded_sink("stderr", sys.stderr)


def report_input_error(message: str) -> None:
    """Write this module's one diagnostic line through a sink a hostile stderr cannot corrupt."""
    advisory_stderr()(f"runtime-assignment.py: {message}\n")


def emit_result(result: dict[str, Any]) -> int:
    """Deliver the one result document, or CLASSIFY the failure instead of inheriting 1 or 120.

    Unlike a diagnostic line, this document IS the evidence, so a stdout that cannot receive it is
    not a lost convenience -- the question was answered and the answer did not arrive. That is an
    internal failure to deliver (exit 1), and it is named rather than left to CPython: `1>&-` starts
    the interpreter with `sys.stdout is None`, so the unguarded `sys.stdout.buffer` raised
    `AttributeError` and exited 1 through an unhandled traceback, and a stdout whose reader had gone
    away exited 120 -- a code this module does not define. Exit 3 still does not apply: nothing was
    refused before an effect, because this tool has no effects to refuse before.

    `canonical_bytes` is `ensure_ascii=True`, so the payload is ASCII and a text stream with no
    `.buffer` -- what an importing caller's `redirect_stdout(StringIO())` installs -- receives
    byte-identical characters rather than being made to fail.
    """
    payload = canonical_bytes(result)
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    write: Any = None
    body: Any = payload
    if buffer is not None and callable(getattr(buffer, "write", None)):
        write, flush = buffer.write, getattr(buffer, "flush", None)
    elif stream is not None and callable(getattr(stream, "write", None)):
        write, flush, body = stream.write, getattr(stream, "flush", None), payload.decode("ascii")
    if write is None:
        report_input_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            "verdict could not be delivered; the verdict itself is unaffected and nothing was written"
        )
        return EXIT_INTERNAL
    try:
        write(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        # Abandoned BEFORE returning: the classification below is worthless if the interpreter's
        # shutdown flush of the same broken stream replaces this exit code with 120.
        abandon_broken_stream("stdout", stream)
        report_input_error(
            f"cannot write the result document to stdout: {exc}; an unknown prefix of it may already "
            "have reached the consumer, so the verdict was derived but not delivered"
        )
        return EXIT_INTERNAL
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules.

    Two defects, both reached only through the grammar path, and both invisible to a run with ordinary
    descriptors. `error` writes usage through `print_usage`, which FALLS BACK TO STDOUT when
    `sys.stderr is None`: under `2>&-` a grammar error kept exit 2 but put usage bytes where this
    module's one result document lives, breaking "an input error emits no result document" bytewise.
    And argparse swallows a failed write while leaving its bytes pending, which is enough for the
    shutdown flush to replace the usage error's 2 with 120. So every argparse line goes through the
    guarded sink for the stream argparse ASKED for, and `error` raises this module's own exit code.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            # argparse resolved `sys.stderr`/`sys.stdout` itself and got None: this process was
            # handed no such stream, so the line is dropped rather than redirected onto the other one.
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


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="runtime-assignment.py",
        description=(
            "Admit or refuse one RuntimeAssignment before spawn, and classify what a runtime receipt "
            "actually served against what was requested. Read-only, offline, subprocess-free, and "
            "effect-free: it authorizes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    exits = (
        "Exit codes: 0 a verdict was derived -- refusing, proposing a Seed, and reporting an "
        "unexplained substitution are all this command SUCCEEDING at deriving one; 2 a supplied "
        "artifact is unreadable, not JSON, or not the document it claims to be, or the arguments "
        "themselves are unusable; 1 an unexpected internal failure, INCLUDING a stdout that cannot "
        "receive the one result document, because a verdict derived and not delivered is not a "
        "success. Implementation Decision 9's 3 and 4 do not apply: a command that causes "
        "no effect can neither refuse before one nor admit one."
    )
    admit = commands.add_parser(
        "admit",
        description=(
            "Derive one pre-spawn verdict: admit-dispatch, refuse-dispatch, or seed-proposal when the "
            "selected host cannot inject both the exact model and the exact effort."
        ),
        epilog=exits,
    )
    admit.add_argument("--request", required=True, help=f"one {REQUEST_SCHEMA} document")
    admit.add_argument(
        "--policy",
        default=None,
        help="runtime-assignment-receipt-v1.json; defaults to the checked-in sibling skill's policy",
    )
    classify = commands.add_parser(
        "classify",
        description=(
            "Classify one served record against its request: exact-match, explained-substitution, or "
            "unexplained-substitution. Anything unprovable is unexplained, which blocks wave "
            "completion."
        ),
        epilog=exits,
    )
    classify.add_argument("--served", required=True, help=f"one {SERVED_SCHEMA} document")
    classify.add_argument(
        "--policy",
        default=None,
        help="runtime-assignment-receipt-v1.json; defaults to the checked-in sibling skill's policy",
    )
    args = parser.parse_args(argv)
    try:
        result, code = admit_command(args) if args.command == "admit" else classify_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    delivered = emit_result(result)
    # An undelivered document is not a derived verdict reaching its caller, so the delivery failure
    # outranks the derived code rather than being reported alongside it.
    return code if delivered == EXIT_OK else delivered


if __name__ == "__main__":
    raise SystemExit(main())
