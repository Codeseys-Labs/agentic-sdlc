#!/usr/bin/env python3
"""Tier-1 self-hashing canonical-JSON gate receipts.

A gate receipt records, in reproducible form, that a specific gate command ran in a specific
worktree against a specific pinned toolchain, and what its exit code was. It is *tamper detection
by re-derivation*, not a security boundary against the same OS user (the same honesty posture as
scripts/validate_bundle.py's runtime-receipt validation). Stdlib only.

Canonical serialization matches the precedent in scripts/validate_bundle.py:412-413 —
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) then sha256 of the utf-8
bytes — so any consumer re-derives the digest byte-for-byte.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """Canonical, reproducible JSON encoding of obj (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_digest(obj: Any) -> str:
    """sha256 hex of the canonical JSON of obj."""
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_receipt(
    *,
    gate: str,
    argv: list[str],
    status: int,
    log_bytes: bytes,
    lock_bytes: bytes,
    cwd: str,
) -> dict[str, Any]:
    """Construct a self-hashing gate receipt.

    Fields (spec G2.6):
    - gate: the exact task string, e.g. "mise run check".
    - argv: the exact argv list executed, proving which command ran (not a paraphrase).
    - status: the integer exit code (0 = pass; the exit code IS the gate).
    - log_digest: sha256 of the captured combined stdout+stderr bytes (tamper-evident log).
    - toolchain_digest: sha256 of mise.lock bytes at run time (binds to the exact pinned toolchain;
      catches "green on drifted pins").
    - cwd: absolute path the gate ran in (ties the receipt to per-path worktree trust).
    - self_digest: sha256 of the canonical JSON of every other field.
    """
    body = {
        "gate": gate,
        "argv": list(argv),
        "status": int(status),
        "log_digest": _sha256_hex(log_bytes),
        "toolchain_digest": _sha256_hex(lock_bytes),
        "cwd": cwd,
    }
    receipt = dict(body)
    receipt["self_digest"] = canonical_digest(body)
    return receipt


def verify_receipt(receipt: dict[str, Any]) -> bool:
    """True iff self_digest re-derives from the canonical JSON of the other fields."""
    stored = receipt.get("self_digest")
    if not isinstance(stored, str):
        return False
    body = {k: v for k, v in receipt.items() if k != "self_digest"}
    return canonical_digest(body) == stored


def verify_toolchain_binding(receipt: dict[str, Any], lock_bytes: bytes) -> bool:
    """True iff the receipt's toolchain_digest matches the given mise.lock bytes."""
    return receipt.get("toolchain_digest") == _sha256_hex(lock_bytes)
