#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate one RuntimeAssignment receipt for internal canonical consistency only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


POLICY_PATH = Path(__file__).parents[1] / "policy" / "runtime-assignment-receipt-v1.json"
ALLOWED_EVIDENCE = {
    "request_injection": {
        "source_kinds": ["immutable_request_receipt"],
        "statuses": ["verified"],
        "schemas": ["launcher-request-evidence/v1"],
    },
    "model_mapping": {
        "source_kinds": ["policy_exact_id_mapping"],
        "statuses": ["unavailable"],
        "schemas": ["runtime-assignment-policy-v1"],
    },
    "transport_readback": {
        "source_kinds": ["transport_readback"],
        "statuses": ["verified", "unavailable"],
        "schemas": ["runtime-assignment-readback/v1"],
    },
}
READBACK_EVIDENCE_FIELDS = (
    "model_readback_evidence",
    "effort_readback_evidence",
    "context_readback_evidence",
)
READBACK_VALUE_KEYS = {
    "effort": "observed_effort",
    "context": "observed_context_form",
}
# A transport that reports an effective value outside the contract's own vocabulary is not
# speaking this contract's language. Such a report is recorded as an unavailable readback; it
# never becomes a verified one.
READBACK_VALUE_VOCABULARIES = {
    "effort": "allowed_efforts",
    "context": "allowed_context_forms",
}
# A verified effort/context readback either agreed with the requested value or diverged from
# it. Both are admissible; the state is recomputed here from the evidence, so a divergence
# cannot be recorded as agreement. Divergence is the only shape in which readback carries
# information a holder of the request could not have written by itself.
EFFECTIVE_VALUE_STATES = ("matches_requested", "diverges_from_requested")
# Divergence is also declared at the top level, so a consumer reading only the receipt's
# summary fields cannot miss that a verified readback reported something other than what was
# requested. Without a verified readback the divergence fact is simply unavailable.
DIVERGENCE_UNAVAILABLE = "unavailable"
EFFECTIVE_DIVERGENCE_STATES = (*EFFECTIVE_VALUE_STATES, DIVERGENCE_UNAVAILABLE)
EFFECTIVE_DIVERGENCE_FIELDS = {
    "effort": "effort_effective_divergence",
    "context": "context_effective_divergence",
}
UNRESOLVED = object()
UNPARSEABLE = object()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_no_duplicate_members(raw: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON member: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=reject_duplicates)


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def exact_object(
    evidence: Any,
    expected_fields: set[str],
    evidence_class: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(evidence, dict):
        errors.append(f"{evidence_class} evidence must be a JSON object")
        return None
    missing = sorted(expected_fields - set(evidence))
    unexpected = sorted(set(evidence) - expected_fields)
    if missing:
        errors.append(f"{evidence_class} evidence missing fields: {', '.join(missing)}")
    if unexpected:
        errors.append(f"{evidence_class} evidence unexpected fields: {', '.join(unexpected)}")
    return None if missing or unexpected else evidence


def typed_evidence(
    evidence: dict[str, Any] | None,
    policy: dict[str, Any],
    evidence_class: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if evidence is None:
        return None
    allowed = policy["allowed_evidence"][evidence_class]
    for field in ("source_kind", "status", "schema"):
        if not is_nonempty_string(evidence.get(field)):
            errors.append(f"{evidence_class} evidence {field} must be a non-empty string")
    if any(not is_nonempty_string(evidence.get(field)) for field in ("source_kind", "status", "schema")):
        return None
    if evidence["source_kind"] not in allowed["source_kinds"]:
        errors.append(f"{evidence_class} evidence source_kind is not allowed")
    if evidence["status"] not in allowed["statuses"]:
        errors.append(f"{evidence_class} evidence status is not allowed")
    if evidence["schema"] not in allowed["schemas"]:
        errors.append(f"{evidence_class} evidence schema is not allowed")
    return evidence


def assignment_binding(receipt: dict[str, Any]) -> dict[str, Any]:
    """Identify the one assignment every evidence object must belong to.

    This is deliberately request-derived: it names *which* assignment the evidence was
    captured for, so evidence cannot be transplanted between receipts. It is never a
    readback claim, and no readback digest may be recomputed from it.
    """
    return {
        "context_form": receipt["requested_context_form"],
        "effort": receipt["requested_effort"],
        "model_id": receipt["resolved_model_id"],
        "provider": receipt["resolved_provider"],
    }


def parse_response_body(response_bytes: str) -> Any:
    """Parse a transport response body, or report that it is not structured at all.

    A readback in this contract is a *structured* adapter response. Freeform text cannot bind
    a value to a position, so it cannot be a verified readback: an honest transport that only
    emits prose must record its readback as status `unavailable` instead.
    """
    try:
        return parse_no_duplicate_members(response_bytes)
    except (ValueError, json.JSONDecodeError):
        return UNPARSEABLE


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve one RFC 6901 JSON pointer against a parsed response body.

    Returns UNRESOLVED for any pointer that does not name an existing location. Only an exact
    resolved location can bind a value: a value found *somewhere* in the bytes proves nothing,
    because a substring can be manufactured by unrelated content (a `highlights` key contains
    the text `high`).
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


def request_echo_forms(receipt: dict[str, Any], requested_value: str) -> tuple[set[str], list[Any]]:
    """The request-derived shapes a holder of the request alone could have written.

    Returned as canonical strings plus the parsed shapes themselves, so an echo is refused on
    its *content* rather than its formatting: whitespace, indentation, quoting, and key order
    are all normalized away before comparison.

    This refuses provably request-derived shapes. It cannot authenticate that any other bytes
    came from the transport — only the external authenticated harness can do that. Bytes
    outside these shapes are recorded, never vouched for.
    """
    requested_effort = receipt["requested_effort"]
    requested_context_form = receipt["requested_context_form"]
    shapes: list[Any] = [
        requested_value,
        assignment_binding(receipt),
        {
            "context_form": requested_context_form,
            "effort": requested_effort,
            "model_id": receipt["requested_model_id"],
        },
        {"effort": requested_effort},
        {"context_form": requested_context_form},
    ]
    return {canonical_json(shape) for shape in shapes}, shapes


def is_request_echo(receipt: dict[str, Any], requested_value: str, response_bytes: str, parsed: Any) -> bool:
    canonical_forms, shapes = request_echo_forms(receipt, requested_value)
    # The bare requested value is an echo whether or not it is quoted as JSON, so it is
    # compared as raw text as well as in canonical form.
    if response_bytes.strip() in canonical_forms | {requested_value}:
        return True
    if parsed is UNPARSEABLE:
        return False
    # Compare canonical-to-canonical: the entire parsed body being one request-derived shape
    # is an echo no matter how it was serialized.
    return canonical_json(parsed) in canonical_forms or any(parsed == shape for shape in shapes)


def construct_receipt(
    *,
    policy: dict[str, Any],
    requested_model_id: str,
    requested_effort: str,
    requested_context_form: str,
    adapter_id: str,
    adapter_version: str,
    adapter_config: Any,
    model_identity_basis: str,
    effort_readback_status: str,
    context_readback_status: str,
    observed_provider: str | None = None,
    observed_model_id: str | None = None,
    observed_effort: str | None = None,
    observed_context_form: str | None = None,
    effort_readback_response_bytes: str | None = None,
    context_readback_response_bytes: str | None = None,
    effort_observed_value_pointer: str | None = None,
    context_observed_value_pointer: str | None = None,
) -> dict[str, Any]:
    provider = policy["allowed_exact_model_ids"].get(requested_model_id)
    if provider is None:
        raise ValueError("requested_model_id is not an allowed exact model ID")

    request_binding = {
        "context_form": requested_context_form,
        "effort": requested_effort,
        "model_id": requested_model_id,
    }
    receipt: dict[str, Any] = {
        "schema_version": policy["schema_version"],
        "requested_model_id": requested_model_id,
        "requested_effort": requested_effort,
        "requested_context_form": requested_context_form,
        "request_injection_status": "verified",
        "request_injection_evidence": {
            "source_kind": "immutable_request_receipt",
            "status": "verified",
            "schema": "launcher-request-evidence/v1",
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "adapter_config_sha256": sha256_json(adapter_config),
            "request_bytes_sha256": sha256_json(request_binding),
        },
        "resolution_state": "resolved",
        "resolved_provider": provider,
        "resolved_model_id": requested_model_id,
        "model_identity_basis": model_identity_basis,
        "model_readback_status": "verified",
        "model_readback_evidence": {},
        "effort_readback_status": effort_readback_status,
        "effort_readback_evidence": {},
        "effort_effective_divergence": DIVERGENCE_UNAVAILABLE,
        "context_readback_status": context_readback_status,
        "context_readback_evidence": {},
        "context_effective_divergence": DIVERGENCE_UNAVAILABLE,
    }
    binding_digest = sha256_json(assignment_binding(receipt))

    if model_identity_basis == "unambiguous_exact_id_mapping":
        receipt["model_readback_evidence"] = {
            "source_kind": "policy_exact_id_mapping",
            "status": "unavailable",
            "schema": "runtime-assignment-policy-v1",
            "reference": policy["model_mapping_reference"],
            "mapped_provider": provider,
            "mapped_model_id": requested_model_id,
            "assignment_binding_sha256": binding_digest,
        }
    elif model_identity_basis == "independent_readback":
        receipt["model_readback_evidence"] = {
            "source_kind": "transport_readback",
            "status": "verified",
            "schema": "runtime-assignment-readback/v1",
            "observed_provider": observed_provider,
            "observed_model_id": observed_model_id,
            "readback_bytes_sha256": sha256_json(
                {"model_id": observed_model_id, "provider": observed_provider}
            ),
            "assignment_binding_sha256": binding_digest,
        }
    else:
        raise ValueError("model_identity_basis is unsupported")

    for name, status, observed_value, response_bytes, pointer in (
        ("effort", effort_readback_status, observed_effort, effort_readback_response_bytes, effort_observed_value_pointer),
        (
            "context",
            context_readback_status,
            observed_context_form,
            context_readback_response_bytes,
            context_observed_value_pointer,
        ),
    ):
        evidence = {
            "source_kind": "transport_readback",
            "status": status,
            "schema": "runtime-assignment-readback/v1",
            "assignment_binding_sha256": binding_digest,
        }
        if status == "verified":
            if not is_nonempty_string(response_bytes):
                raise ValueError(
                    f"verified {name} readback requires the transport response bytes; "
                    "a requested value is not readback"
                )
            if not isinstance(pointer, str):
                raise ValueError(
                    f"verified {name} readback requires observed_value_pointer naming where the "
                    "transport reported the effective value"
                )
            vocabulary = policy[READBACK_VALUE_VOCABULARIES[name]]
            if observed_value not in vocabulary:
                raise ValueError(
                    f"verified {name} readback observed value is outside the contract vocabulary; "
                    "record it as an unavailable readback instead"
                )
            requested_value = requested_effort if name == "effort" else requested_context_form
            evidence[READBACK_VALUE_KEYS[name]] = observed_value
            evidence["response_bytes"] = response_bytes
            evidence["observed_value_pointer"] = pointer
            evidence["readback_bytes_sha256"] = sha256_text(response_bytes)
            evidence["effective_value_state"] = (
                "matches_requested" if observed_value == requested_value else "diverges_from_requested"
            )
            receipt[EFFECTIVE_DIVERGENCE_FIELDS[name]] = evidence["effective_value_state"]
        elif status != "unavailable":
            raise ValueError(f"{name}_readback_status must be verified or unavailable")
        receipt[f"{name}_readback_evidence"] = evidence

    expected_order = tuple(policy["canonical_receipt_fields"])
    if tuple(receipt) != expected_order:
        raise ValueError("constructed receipt does not match canonical field order")
    errors = receipt_errors(receipt, policy)
    if errors:
        raise ValueError("invalid constructed receipt: " + "; ".join(errors))
    return receipt


def request_evidence_errors(receipt: dict[str, Any], policy: dict[str, Any], errors: list[str]) -> None:
    required = {
        "source_kind",
        "status",
        "schema",
        "adapter_id",
        "adapter_version",
        "adapter_config_sha256",
        "request_bytes_sha256",
    }
    evidence = typed_evidence(
        exact_object(receipt["request_injection_evidence"], required, "request injection", errors),
        policy,
        "request_injection",
        errors,
    )
    if evidence is None:
        return
    if not is_nonempty_string(evidence["adapter_id"]) or not is_nonempty_string(evidence["adapter_version"]):
        errors.append("request injection adapter ID and version must be non-empty strings")
    for field in ("adapter_config_sha256", "request_bytes_sha256"):
        if not is_sha256(evidence[field]):
            errors.append(f"request injection evidence {field} must be a lowercase SHA-256 digest")
    expected_request = {
        "context_form": receipt["requested_context_form"],
        "effort": receipt["requested_effort"],
        "model_id": receipt["requested_model_id"],
    }
    if evidence["request_bytes_sha256"] != sha256_json(expected_request):
        errors.append("request injection evidence does not bind the requested model/effort/context bytes")


def model_evidence_errors(receipt: dict[str, Any], policy: dict[str, Any], errors: list[str]) -> None:
    if receipt["model_identity_basis"] == "unambiguous_exact_id_mapping":
        required = {
            "source_kind",
            "status",
            "schema",
            "reference",
            "mapped_provider",
            "mapped_model_id",
            "assignment_binding_sha256",
        }
        evidence = typed_evidence(
            exact_object(receipt["model_readback_evidence"], required, "model mapping", errors),
            policy,
            "model_mapping",
            errors,
        )
        if evidence is not None:
            if evidence["reference"] != policy["model_mapping_reference"]:
                errors.append("mapping-only model evidence requires the policy mapping reference")
            if evidence["mapped_provider"] != receipt["resolved_provider"] or evidence["mapped_model_id"] != receipt["resolved_model_id"]:
                errors.append("model mapping evidence does not bind the resolved provider/model to the receipt")
        return
    if receipt["model_identity_basis"] != "independent_readback":
        errors.append("model_identity_basis is unsupported")
        return

    required = {
        "source_kind",
        "status",
        "schema",
        "observed_provider",
        "observed_model_id",
        "readback_bytes_sha256",
        "assignment_binding_sha256",
    }
    evidence = typed_evidence(
        exact_object(receipt["model_readback_evidence"], required, "model readback", errors),
        policy,
        "transport_readback",
        errors,
    )
    if evidence is None:
        return
    if evidence["status"] != "verified":
        errors.append("independent model readback evidence must be verified")
    for field in ("observed_provider", "observed_model_id"):
        if not is_nonempty_string(evidence[field]):
            errors.append(f"model readback evidence {field} must be a non-empty string")
    if not is_sha256(evidence["readback_bytes_sha256"]):
        errors.append("model readback evidence readback_bytes_sha256 must be a lowercase SHA-256 digest")
    expected = {"model_id": receipt["resolved_model_id"], "provider": receipt["resolved_provider"]}
    if evidence["observed_provider"] != receipt["resolved_provider"] or evidence["observed_model_id"] != receipt["resolved_model_id"]:
        errors.append("model readback evidence does not bind observed provider/model to the receipt")
    if evidence["readback_bytes_sha256"] != sha256_json(expected):
        errors.append("model readback evidence digest does not bind the resolved provider/model")


def readback_evidence_errors(name: str, receipt: dict[str, Any], policy: dict[str, Any], errors: list[str]) -> None:
    status = receipt[f"{name}_readback_status"]
    value_key = READBACK_VALUE_KEYS[name]
    divergence_field = EFFECTIVE_DIVERGENCE_FIELDS[name]
    declared_divergence = receipt[divergence_field]
    if status == "unavailable":
        required = {"source_kind", "status", "schema", "assignment_binding_sha256"}
        evidence = typed_evidence(
            exact_object(receipt[f"{name}_readback_evidence"], required, f"{name} readback", errors),
            policy,
            "transport_readback",
            errors,
        )
        if evidence is not None and evidence["status"] != "unavailable":
            errors.append(f"{name} unavailable readback evidence must be unavailable")
        if declared_divergence != DIVERGENCE_UNAVAILABLE:
            errors.append(
                f"{divergence_field} must equal {DIVERGENCE_UNAVAILABLE} when the {name} readback "
                "is unavailable"
            )
        return
    if status != "verified":
        errors.append(f"{name}_readback_status must be verified or unavailable")
        return

    required = {
        "source_kind",
        "status",
        "schema",
        value_key,
        "response_bytes",
        "observed_value_pointer",
        "readback_bytes_sha256",
        "effective_value_state",
        "assignment_binding_sha256",
    }
    evidence = typed_evidence(
        exact_object(receipt[f"{name}_readback_evidence"], required, f"{name} readback", errors),
        policy,
        "transport_readback",
        errors,
    )
    if evidence is None:
        return
    if evidence["status"] != "verified":
        errors.append(f"{name} verified readback evidence must be verified")
    if not is_nonempty_string(evidence[value_key]):
        errors.append(f"{name} readback evidence {value_key} must be a non-empty string")
    if not is_nonempty_string(evidence["response_bytes"]):
        errors.append(f"{name} readback evidence response_bytes must be a non-empty string")
    if not isinstance(evidence["observed_value_pointer"], str):
        errors.append(f"{name} readback evidence observed_value_pointer must be a JSON pointer string")
    if not is_sha256(evidence["readback_bytes_sha256"]):
        errors.append(f"{name} readback evidence readback_bytes_sha256 must be a lowercase SHA-256 digest")
    if (
        not is_nonempty_string(evidence[value_key])
        or not is_nonempty_string(evidence["response_bytes"])
        or not isinstance(evidence["observed_value_pointer"], str)
    ):
        return

    # The digest binds the transport's own response bytes. It is never recomputed from a
    # requested value, so it cannot be produced by a holder of the request alone.
    if is_sha256(evidence["readback_bytes_sha256"]) and evidence["readback_bytes_sha256"] != sha256_text(
        evidence["response_bytes"]
    ):
        errors.append(f"{name} readback evidence digest does not bind the transport response bytes")

    # The observed value binds to an exact position in the parsed response, never to a
    # substring of the raw bytes: `{"highlights": [...]}` contains the text `high` without the
    # transport ever having reported `high` as the effective value.
    parsed = parse_response_body(evidence["response_bytes"])
    if parsed is UNPARSEABLE:
        errors.append(
            f"{name} readback evidence response_bytes must parse as JSON; freeform transport "
            f"text cannot bind an effective {name} and must be recorded as status unavailable"
        )
    else:
        resolved = resolve_json_pointer(parsed, evidence["observed_value_pointer"])
        if resolved is UNRESOLVED:
            errors.append(
                f"{name} readback evidence observed_value_pointer does not resolve in the "
                "transport response"
            )
        elif not isinstance(resolved, str):
            errors.append(
                f"{name} readback evidence observed_value_pointer resolves to a non-string value"
            )
        elif resolved != evidence[value_key]:
            errors.append(
                f"{name} readback evidence {value_key} does not equal the value the transport "
                "reported at observed_value_pointer"
            )

    requested_value = receipt["requested_effort"] if name == "effort" else receipt["requested_context_form"]
    if is_request_echo(receipt, requested_value, evidence["response_bytes"], parsed):
        errors.append(f"{name} readback response bytes are a request echo, not a transport readback")

    # A transport reporting a value this contract does not define is not speaking the
    # contract's language, so its report cannot be a verified readback of it.
    if evidence[value_key] not in policy[READBACK_VALUE_VOCABULARIES[name]]:
        errors.append(
            f"{name} readback evidence {value_key} is outside the contract {name} vocabulary; "
            "an out-of-vocabulary transport report must be recorded as status unavailable"
        )

    # A divergent effective value is admissible: it is recorded, never refused, and never
    # upgraded to agreement. Agreement is the weaker record, so it may not be claimed for a
    # value that in fact diverged.
    observed_state = (
        "matches_requested" if evidence[value_key] == requested_value else "diverges_from_requested"
    )
    if evidence["effective_value_state"] not in EFFECTIVE_VALUE_STATES:
        errors.append(f"{name} readback evidence effective_value_state is not an allowed state")
    elif evidence["effective_value_state"] != observed_state:
        errors.append(
            f"{name} readback evidence effective_value_state does not record the observed "
            f"{name} against the requested {name}"
        )
    # Divergence recorded only inside the evidence object is invisible to a consumer reading
    # the receipt's summary fields, so the top level must declare the same fact.
    if declared_divergence != observed_state:
        errors.append(
            f"{divergence_field} does not declare the divergence the {name} readback evidence "
            "records"
        )


def cross_field_readback_errors(receipt: dict[str, Any], errors: list[str]) -> None:
    # This digest is request-derived on purpose: it identifies the assignment the evidence
    # was captured for and refuses transplants between receipts. It is not a readback claim,
    # so a divergent effective effort or context still binds to the same assignment.
    expected_digest = sha256_json(assignment_binding(receipt))
    for field in READBACK_EVIDENCE_FIELDS:
        evidence = receipt[field]
        if not isinstance(evidence, dict) or "assignment_binding_sha256" not in evidence:
            continue
        digest = evidence["assignment_binding_sha256"]
        if not is_sha256(digest):
            errors.append(f"{field} assignment_binding_sha256 must be a lowercase SHA-256 digest")
        elif digest != expected_digest:
            errors.append(f"{field} cross-field assignment binding does not match the receipt")


def receipt_errors(receipt: Any, policy: dict[str, Any]) -> list[str]:
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]

    required_fields = frozenset(policy["canonical_receipt_fields"])
    errors: list[str] = []
    keys = set(receipt)
    missing = sorted(required_fields - keys)
    unexpected = sorted(keys - required_fields)
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected fields: {', '.join(unexpected)}")
    if missing or unexpected:
        return errors

    if policy.get("allowed_evidence") != ALLOWED_EVIDENCE:
        return ["policy allowed_evidence vocabulary differs from the source-pinned contract"]

    evidence_fields = {
        "request_injection_evidence",
        "model_readback_evidence",
        "effort_readback_evidence",
        "context_readback_evidence",
    }
    for field in required_fields - evidence_fields:
        if not is_nonempty_string(receipt[field]):
            errors.append(f"{field} must be a non-empty string")
    if errors:
        return errors

    model_map = policy["allowed_exact_model_ids"]
    if receipt["schema_version"] != policy["schema_version"]:
        errors.append("unsupported schema_version")
    if receipt["requested_model_id"] not in model_map:
        errors.append("requested_model_id is not an allowed exact model ID")
    if receipt["requested_effort"] not in policy["allowed_efforts"]:
        errors.append("requested_effort is not allowed")
    if receipt["requested_context_form"] not in policy["allowed_context_forms"]:
        errors.append("requested_context_form is not allowed")
    if receipt["request_injection_status"] != "verified":
        errors.append("request_injection_status must equal verified")
    if receipt["resolution_state"] != "resolved":
        errors.append("resolution_state must equal resolved")
    if receipt["model_readback_status"] != "verified":
        errors.append("model_readback_status must equal verified")
    if receipt["resolved_model_id"] != receipt["requested_model_id"]:
        errors.append("resolved_model_id must match the immutable injected exact model ID")
    for field in EFFECTIVE_DIVERGENCE_FIELDS.values():
        if receipt[field] not in EFFECTIVE_DIVERGENCE_STATES:
            errors.append(f"{field} is not an allowed divergence state")

    expected_provider = model_map.get(receipt["requested_model_id"])
    if expected_provider and receipt["resolved_provider"] != expected_provider:
        errors.append("resolved_provider does not match the exact model ID mapping")

    tuple_key = [receipt["requested_model_id"], receipt["requested_effort"], receipt["requested_context_form"]]
    if tuple_key not in policy["certified_request_tuples"]:
        errors.append("requested model/effort/context tuple is not certified")

    request_evidence_errors(receipt, policy, errors)
    model_evidence_errors(receipt, policy, errors)
    readback_evidence_errors("effort", receipt, policy, errors)
    readback_evidence_errors("context", receipt, policy, errors)
    cross_field_readback_errors(receipt, errors)
    return errors


def main() -> int:
    try:
        policy = parse_no_duplicate_members(POLICY_PATH.read_text(encoding="utf-8"))
        receipt = parse_no_duplicate_members(sys.stdin.read())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(canonical_json({"errors": [str(exc)], "status": "invalid"}))
        return 2

    errors = receipt_errors(receipt, policy)
    if errors:
        print(canonical_json({"errors": errors, "status": "invalid"}))
        return 1

    digest = sha256_json(receipt)
    print(canonical_json({"digest_sha256": digest, "status": "validated"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
