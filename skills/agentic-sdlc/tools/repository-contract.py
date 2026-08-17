#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only reader for the RepositoryContractManifest at `.agentic-sdlc/repo.toml`.

ADR-0022 decision 2 says that file is *tracked*, and this module reads it at that path.
It does NOT verify trackedness: proving it needs Git, and this module runs no subprocess.
Callers that need "tracked" as a fact must establish it separately -- the activation
engine already refuses a dirty manifest through its Git projection.

The fields are the portable intent enumerated in
`docs/plans/claude-code-first-harness/issues/09-define-repository-activation-contract.md`
-- schema version, canonical guidance, queue adapter, ADR/glossary locations,
authoritative gate, worktree and integration policy, CI expectation, and the enabled
writing profile. Schema `@1` is deliberately a FLAT, all-strings subset of that text:
other accepted specs already anticipate structure this version cannot express (a tracked
rightsizing table, tunable numeric thresholds, plural writing rules), so those arrive
with a schema bump rather than by loosening `@1`.

This module reads and validates. It never writes, never runs a gate, never contacts a
provider, and never asserts readiness. Implementation Decision 10 is explicit that the
manifest is not ownership, tool, trust, route, or readiness proof, so a manifest that
tries to claim any of those is REFUSED by name rather than read and quietly ignored --
a silently-tolerated claim is how a portable intent file turns into forged evidence.

Local ownership, hashes, tool identities, and trust state live in the machine-local
receipt plane instead, and readiness is a separate assessment this module does not make.

Custody is exact and fd-based. Every component of the path is opened with `O_NOFOLLOW`
and the bytes are read from the verified descriptor, because lstat-ing only the final
component lets a symlinked *parent* redirect custody outside the repository entirely,
and a second path lookup after a check can be swapped underneath it.

Exit codes follow Implementation Decision 9: 0 valid, 1 internal, 2 grammar or schema,
3 clean refusal before any effect. Custody refusals are clean refusals and return 3;
malformed bytes and schema violations return 2. `activation-planner.py` maps refusals to
1 instead, a mapping that predates the decision.

There is no `scripts/` compatibility shim yet, because nothing invokes this as
`scripts/repository_contract.py`. Add one when a mise task or dispatcher needs it.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tomllib
from pathlib import Path
from typing import Any

RESULT_SCHEMA = "agentic-sdlc/repository-contract-result@1"
MANIFEST_SCHEMA = "agentic-sdlc/repository-contract@1"
STATE_DIRECTORY_NAME = ".agentic-sdlc"
REPO_MANIFEST_NAME = "repo.toml"
MANIFEST_RELATIVE_PATH = f"{STATE_DIRECTORY_NAME}/{REPO_MANIFEST_NAME}"

REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "canonical_guidance",
        "queue_adapter",
        "adr_location",
        "glossary_location",
        "authoritative_gate",
        "worktree_policy",
        "integration_policy",
        "ci_expectation",
        "writing_profile",
    }
)

# Substrings the manifest may not use as field names. Portable intent that asserts one of
# these is claiming evidence it cannot hold.
PROHIBITED_CLAIM_TOKENS = ("readiness", "ready", "ownership", "owned", "trust", "route", "tool")


# Implementation Decision 9: 2 is grammar or schema, 3 is a clean refusal before effect.
SCHEMA_CODE = 2
CUSTODY_CODE = 3


class ContractError(ValueError):
    """A refusal carrying the status, the reason, and the exit code."""

    def __init__(self, status: str, reason: str, code: int = SCHEMA_CODE) -> None:
        super().__init__(reason)
        self.status, self.reason, self.code = status, reason, code


def canonical_bytes(value: Any) -> bytes:
    """Canonical JSON plus a trailing newline, matching the activation family."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("refused", f"invalid {label}")
    return value


def validate_contract(value: Any) -> dict[str, Any]:
    """Exact closed key set, all string values, no prohibited claim."""
    if not isinstance(value, dict):
        raise ContractError("refused", "contract must be a table")
    # Only unrecognized keys are token-screened. Screening every key would refuse a future
    # legitimate field whose name merely contains a token -- `toolchain_expectation`
    # contains "tool", `trusted_config_paths` contains "trust" -- and would do it with a
    # misleading reason. The closed key set below is what actually bounds the schema; this
    # loop exists so a prohibited claim is refused BY NAME instead of as "unknown field".
    for name in sorted(set(value) - REQUIRED_FIELDS):
        if any(token in name.lower() for token in PROHIBITED_CLAIM_TOKENS):
            raise ContractError("refused", f"contract must not claim {name}")
    if set(value) != REQUIRED_FIELDS:
        missing = sorted(REQUIRED_FIELDS - set(value))
        unknown = sorted(set(value) - REQUIRED_FIELDS)
        detail = f"missing {missing}" if missing else f"unknown {unknown}"
        raise ContractError("refused", f"invalid contract schema: {detail}")
    if value["schema"] != MANIFEST_SCHEMA:
        raise ContractError("refused", "unsupported contract schema")
    for name in sorted(REQUIRED_FIELDS):
        _text(value[name], name)
    return dict(value)


def _open_at(name: str, dir_fd: int, *, directory: bool) -> int:
    """Open one path component, refusing symlinks and never blocking on a FIFO."""
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    return os.open(name, flags, dir_fd=dir_fd)


def read_manifest_bytes(target: Path) -> bytes | None:
    """Read the manifest through verified descriptors, or None when there is none.

    Each component is opened with O_NOFOLLOW, so a symlinked `.agentic-sdlc` cannot
    redirect custody outside the repository, and the bytes come from the same descriptor
    that was type-checked, so there is no second lookup to swap. A missing component is
    absent; any other failure is a refusal, because reporting an unreadable manifest as
    `absent` would tell a caller there is no portable intent when there is one.
    """
    try:
        target_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except FileNotFoundError:
        raise ContractError("refused", "target does not exist", CUSTODY_CODE) from None
    except OSError as exc:
        raise ContractError("refused", "cannot open target", CUSTODY_CODE) from exc
    try:
        try:
            state_fd = _open_at(STATE_DIRECTORY_NAME, target_fd, directory=True)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ContractError("refused", f"unsafe {STATE_DIRECTORY_NAME}", CUSTODY_CODE) from exc
        try:
            try:
                manifest_fd = _open_at(REPO_MANIFEST_NAME, state_fd, directory=False)
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise ContractError("refused", f"unsafe {MANIFEST_RELATIVE_PATH}", CUSTODY_CODE) from exc
            try:
                if not stat.S_ISREG(os.fstat(manifest_fd).st_mode):
                    raise ContractError("refused", f"{MANIFEST_RELATIVE_PATH} must be a regular file", CUSTODY_CODE)
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(manifest_fd, 65536)
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
            except OSError as exc:
                raise ContractError("refused", f"cannot read {MANIFEST_RELATIVE_PATH}", CUSTODY_CODE) from exc
            finally:
                os.close(manifest_fd)
        finally:
            os.close(state_fd)
    finally:
        os.close(target_fd)


def parse_contract(raw: bytes) -> dict[str, Any]:
    """Decode and validate manifest bytes. Grammar and schema failures, not custody."""
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ContractError("refused", f"{MANIFEST_RELATIVE_PATH} is not UTF-8") from exc
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ContractError("refused", f"malformed {MANIFEST_RELATIVE_PATH}") from exc
    return validate_contract(parsed)


def _result(status: str, target: Path, *, contract: dict[str, Any] | None = None, reasons: list[str] | None = None, code: int = 0) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "command": "inspect",
        "status": status,
        "exit_code": code,
        "target": str(target),
        "contract": contract,
        "reasons": reasons or [],
    }


def inspect_command(target: Path) -> tuple[dict[str, Any], int]:
    """Report the tracked contract, or that there is none. Writes nothing."""
    target = Path(target)
    try:
        if not target.is_absolute():
            raise ContractError("refused", "target must be an absolute path")
        raw = read_manifest_bytes(target)
        if raw is None:
            return _result("absent", target), 0
        return _result("valid", target, contract=parse_contract(raw)), 0
    except ContractError as exc:
        return _result(exc.status, target, reasons=[exc.reason], code=exc.code), exc.code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the tracked repository contract manifest.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)
    result, code = inspect_command(args.target)
    sys.stdout.buffer.write(canonical_bytes(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
