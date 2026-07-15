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
        "request_injection_source",
        "request_injection_evidence",
        "resolution_state",
        "resolved_provider",
        "resolved_model_id",
        "model_readback_status",
        "model_identity_basis",
        "model_readback_source",
        "model_readback_evidence",
        "effort_readback_status",
        "effort_readback_source",
        "effort_readback_evidence",
        "context_readback_status",
        "context_readback_source",
        "context_readback_evidence",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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

    for field in sorted(REQUIRED_FIELDS):
        if not is_nonempty_string(receipt[field]):
            errors.append(f"{field} must be a non-empty string")
    if errors:
        return errors

    unavailable = policy["unavailable_marker"]
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
    if receipt["model_identity_basis"] not in {"independent_readback", "unambiguous_exact_id_mapping"}:
        errors.append("model_identity_basis is unsupported")

    if receipt["request_injection_source"] == unavailable or receipt["request_injection_evidence"] == unavailable:
        errors.append("request injection must have immutable source and evidence")
    if "default" in receipt["request_injection_source"].lower():
        errors.append("host-default request injection is forbidden")
    if receipt["resolved_model_id"] != receipt["requested_model_id"]:
        errors.append("resolved_model_id must match the immutable injected exact model ID")

    expected_provider = model_map.get(receipt["requested_model_id"])
    if expected_provider and receipt["resolved_provider"] != expected_provider:
        errors.append("resolved_provider does not match the exact model ID mapping")

    if receipt["model_identity_basis"] == "independent_readback":
        if receipt["model_readback_source"] == unavailable or receipt["model_readback_evidence"] == unavailable:
            errors.append("independent model readback requires source and evidence")
        if receipt["model_readback_source"] in {"requested_model_id", "request_injection_source"}:
            errors.append("requested or request-injection values cannot become model readback")
    else:
        if receipt["model_readback_source"] != unavailable:
            errors.append("mapping-only model identity requires unavailable_in_transport source")
        if receipt["model_readback_evidence"] != policy["model_mapping_evidence"]:
            errors.append("mapping-only model identity requires the policy mapping evidence")

    for name in ("effort", "context"):
        status = receipt[f"{name}_readback_status"]
        source = receipt[f"{name}_readback_source"]
        evidence = receipt[f"{name}_readback_evidence"]
        if status not in {"verified", "unavailable"}:
            errors.append(f"{name}_readback_status must be verified or unavailable")
            continue
        if status == "unavailable":
            if source != unavailable or evidence != unavailable:
                errors.append(f"unavailable {name} readback requires unavailable_in_transport markers")
        elif source == unavailable or evidence == unavailable:
            errors.append(f"verified {name} readback requires independent source and evidence")
        elif source in {"requested_effort", "requested_context_form", "request_injection_source"}:
            errors.append(f"requested or injection values cannot become {name} readback")

    return errors


def main() -> int:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        receipt = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as exc:
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
