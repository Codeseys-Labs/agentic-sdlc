#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Admit or deny one RuntimeAssignment receipt without launching a worker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


POLICY_PATH = Path(__file__).parents[1] / "policy" / "runtime-assignment-receipt-v1.json"
REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "requested_model_id",
        "requested_effort",
        "requested_context_form",
        "request_injection_status",
        "request_injection_evidence",
        "resolution_state",
        "resolved_provider",
        "resolved_model_id",
        "model_readback_status",
        "model_identity_basis",
        "model_readback_evidence",
        "effort_readback_status",
        "effort_readback_evidence",
        "context_readback_status",
        "context_readback_evidence",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def validate_evidence(
    evidence: Any,
    policy: dict[str, Any],
    evidence_class: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(evidence, dict):
        errors.append(f"{evidence_class} evidence must be a JSON object")
        return None
    allowed = policy["allowed_evidence"][evidence_class]
    for field in ("source_kind", "status", "schema"):
        if not is_nonempty_string(evidence.get(field)):
            errors.append(f"{evidence_class} evidence {field} must be a non-empty string")
    if errors:
        return None
    if evidence["source_kind"] not in allowed["source_kinds"]:
        errors.append(f"{evidence_class} evidence source_kind is not allowed")
    if evidence["status"] not in allowed["statuses"]:
        errors.append(f"{evidence_class} evidence status is not allowed")
    if evidence["schema"] not in allowed["schemas"]:
        errors.append(f"{evidence_class} evidence schema is not allowed")
    return evidence


def request_evidence_errors(receipt: dict[str, Any], policy: dict[str, Any], errors: list[str]) -> None:
    evidence = validate_evidence(receipt["request_injection_evidence"], policy, "request_injection", errors)
    if evidence is None:
        return
    required = {"source_kind", "status", "schema", "adapter_id", "adapter_version", "adapter_config_sha256", "request_bytes_sha256"}
    unexpected = sorted(set(evidence) - required)
    missing = sorted(required - set(evidence))
    if missing:
        errors.append(f"request injection evidence missing fields: {', '.join(missing)}")
    if unexpected:
        errors.append(f"request injection evidence unexpected fields: {', '.join(unexpected)}")
    if missing or unexpected:
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
    if evidence.get("request_bytes_sha256") != sha256_json(expected_request):
        errors.append("request injection evidence does not bind the requested model/effort/context bytes")


def model_evidence_errors(receipt: dict[str, Any], policy: dict[str, Any], errors: list[str]) -> None:
    evidence = receipt["model_readback_evidence"]
    if receipt["model_identity_basis"] == "unambiguous_exact_id_mapping":
        evidence = validate_evidence(evidence, policy, "model_mapping", errors)
        if evidence is None:
            return
        if set(evidence) != {"source_kind", "status", "schema", "reference"}:
            errors.append("mapping-only model evidence must contain only the policy reference fields")
        elif evidence["reference"] != policy["model_mapping_reference"]:
            errors.append("mapping-only model evidence requires the policy mapping reference")
        return
    if receipt["model_identity_basis"] == "independent_readback":
        evidence = validate_evidence(evidence, policy, "transport_readback", errors)
        if evidence is None:
            return
        if evidence["status"] != "verified":
            errors.append("independent model readback evidence must be verified")
        return
    errors.append("model_identity_basis is unsupported")


def readback_evidence_errors(name: str, receipt: dict[str, Any], policy: dict[str, Any], errors: list[str]) -> None:
    status = receipt[f"{name}_readback_status"]
    evidence = validate_evidence(receipt[f"{name}_readback_evidence"], policy, "transport_readback", errors)
    if status not in {"verified", "unavailable"}:
        errors.append(f"{name}_readback_status must be verified or unavailable")
    if evidence is not None and evidence["status"] != status:
        errors.append(f"{name} readback status must match structured evidence status")


def receipt_errors(receipt: Any, policy: dict[str, Any]) -> list[str]:
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]

    errors: list[str] = []
    keys = set(receipt)
    missing = sorted(REQUIRED_FIELDS - keys)
    unexpected = sorted(keys - REQUIRED_FIELDS)
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected fields: {', '.join(unexpected)}")
    if missing or unexpected:
        return errors

    for field in REQUIRED_FIELDS - {"request_injection_evidence", "model_readback_evidence", "effort_readback_evidence", "context_readback_evidence"}:
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
    return errors


def main() -> int:
    try:
        policy = parse_no_duplicate_members(POLICY_PATH.read_text(encoding="utf-8"))
        receipt = parse_no_duplicate_members(sys.stdin.read())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(canonical_json({"errors": [str(exc)], "status": "denied"}))
        return 2

    errors = receipt_errors(receipt, policy)
    if errors:
        print(canonical_json({"errors": errors, "status": "denied"}))
        return 1

    digest = hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()
    print(canonical_json({"digest_sha256": digest, "status": "admitted"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
