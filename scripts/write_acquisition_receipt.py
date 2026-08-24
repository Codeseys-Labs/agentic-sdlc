#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Seal one ``release-candidate-acquisition-receipt/v1`` over an already-placed candidate root.

WHY THIS EXISTS.  ``ccodex sdlc install --host claude`` and ``ccodex sdlc update`` admit exactly
one sealed acquisition receipt and the candidate root it names.  Nothing else produces that
document, so without this module both verbs refuse by naming a command no longer in the tree.
This module is that producer, and only that: it copies nothing, extracts nothing, installs
nothing, and activates nothing.

THE OBLIGATION IT CARRIES.  Before it seals, it RE-HASHES every entry at ``--root`` against that
root's own ``manifest.json`` -- both directions, plus symlink targets and node types -- and
refuses by name on the first disagreement.  A receipt is a statement about bytes, so a producer
that has not digested the bytes it points at is asserting provenance it never observed.  That is
the c5ea877 lesson: a timestamp or identity witness cannot distinguish a same-length replacement,
and the control that held was digesting exactly the bytes being published against an admitted
digest.

DERIVED FIELDS, stated because the schema is closed and two of its fields no longer have the
producers they were named for.  The six-phase journal and the plan record are gone with the
acquisition engine, so:

  * ``plan_sha256`` is the sha256 of the root's ``manifest.json`` bytes -- the inventory this
    receipt attests to.
  * ``journal_sha256`` is the sha256 over the canonical JSON of the exact path -> digest map this
    run verified.

Both are re-derivable by any reader holding the root, which the fabricated digests they replace
were not.  ``installed_at`` is bookkeeping, not evidence.

THE WRITE.  Create-only (``O_EXCL``, plus ``O_NOFOLLOW`` where the platform defines it -- with
``O_CREAT | O_EXCL`` a path naming a symlink, even a dangling one, already fails ``EEXIST``),
fsynced, then READ BACK and compared in full
before this run reports success -- seed ``agentic-sdlc-ba1a``'s remedy, carried into the
replacement rather than deleted with its subject.  A readback that disagrees is exit 4 and the
file is left in place: removing it would be a second effect, and a receipt this run cannot vouch
for is not admissible evidence.  A sealed receipt is evidence that a
root was verified against its manifest at one instant; it is not authorization to install, to
publish, or to claim a release, and the schema's own ``release_claim``/``public_channel``/
``support`` constants keep saying so inside the seal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXIT_OK = 0
#: A clean refusal BEFORE the receipt exists.
EXIT_REFUSED = 3
#: The receipt file exists and this run cannot say what it holds.
EXIT_UNKNOWN = 4

RECEIPT_SCHEMA = "release-candidate-acquisition-receipt/v1"
RECEIPT_KEYS = (
    "activation",
    "archive_sha256",
    "candidate_root_absolute_physical_path",
    "effect_state",
    "installed_at",
    "journal_sha256",
    "operation_id",
    "plan_sha256",
    "public_channel",
    "record_sha256",
    "release_claim",
    "schema_version",
    "selection",
    "support",
    "terminal_phase",
)
RECEIPT_CONSTANTS = {
    "activation": "absent",
    "effect_state": "complete",
    "public_channel": None,
    "release_claim": "none",
    "schema_version": RECEIPT_SCHEMA,
    "selection": "absent",
    "support": "unsupported",
    "terminal_phase": "installed-unselected",
}
RECEIPT_SEGMENTS = ("agentic-sdlc", "acquisition", "receipts")
CANDIDATE_SEGMENTS = ("agentic-sdlc", "acquisition", "candidates")
CANDIDATE_LEAF = "root"
RECEIPT_LAYOUT = "$XDG_STATE_HOME/" + "/".join(RECEIPT_SEGMENTS) + "/<archive-sha256>.json"
CANDIDATE_ROOT_LAYOUT = (
    "$XDG_DATA_HOME/" + "/".join(CANDIDATE_SEGMENTS) + f"/<archive-sha256>/{CANDIDATE_LEAF}"
)
MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "release-candidate/v1"
_UTC_INSTANT = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")


class Refusal(RuntimeError):
    pass


class UnknownEffect(RuntimeError):
    """The receipt exists and its content cannot be vouched for; never reported as a success."""


def canonical(document: Any) -> bytes:
    return (
        json.dumps(document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("ascii")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def node_kind(path: Path) -> str:
    item = path.lstat()
    if stat.S_ISLNK(item.st_mode):
        return "symlink"
    if stat.S_ISDIR(item.st_mode):
        return "dir"
    if stat.S_ISREG(item.st_mode):
        return "file"
    raise Refusal(f"the payload node {path} is neither a file, a directory, nor a symlink")


def verify_root(root: Path) -> tuple[str, dict[str, str]]:
    """Re-hash the whole root against its own manifest, and return the manifest and file digests."""
    manifest_path = root / MANIFEST_NAME
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"the candidate manifest {manifest_path} is unreadable or not JSON: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise Refusal(f"the candidate manifest {manifest_path} does not declare {MANIFEST_SCHEMA}")
    rows = manifest.get("inventory")
    if not isinstance(rows, list) or not rows:
        raise Refusal(f"the candidate manifest {manifest_path} carries no inventory to verify against")
    inventoried: dict[str, dict[str, Any]] = {}
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not row["path"]:
            raise Refusal(f"candidate manifest inventory row {ordinal} names no relative path")
        if row["path"] in inventoried:
            raise Refusal(f"the candidate manifest inventories {row['path']!r} twice")
        inventoried[row["path"]] = row
    observed = {
        child.relative_to(root).as_posix(): child
        for child in root.rglob("*")
        if child.relative_to(root).as_posix() != MANIFEST_NAME
    }
    for name in sorted(set(observed) - set(inventoried)):
        raise Refusal(
            f"the candidate root carries {name!r}, which its manifest does not inventory, so this"
            " receipt would attest to bytes the payload's own identity does not cover"
        )
    for name in sorted(set(inventoried) - set(observed)):
        raise Refusal(
            f"the candidate manifest inventories {name!r}, which is absent from the root, so the"
            " root is not the payload its manifest describes"
        )
    digests: dict[str, str] = {}
    for name in sorted(observed):
        path, row = observed[name], inventoried[name]
        kind = node_kind(path)
        if row.get("type") != kind:
            raise Refusal(
                f"the candidate root node {name!r} is a {kind} while its manifest row declares"
                f" {row.get('type')!r}"
            )
        if kind == "file":
            digest = sha256_file(path)
            if digest != row.get("sha256"):
                raise Refusal(
                    f"the candidate root file {name!r} digests to {digest} but its manifest row"
                    f" records {row.get('sha256')!r}"
                )
            digests[name] = digest
        elif kind == "symlink":
            target = os.readlink(path)
            if target != row.get("target"):
                raise Refusal(
                    f"the candidate root symlink {name!r} points at {target!r} but its manifest row"
                    f" records {row.get('target')!r}"
                )
    return hashlib.sha256(raw).hexdigest(), digests


def resolve_archive_digest(archive: Path | None, supplied: str | None) -> str:
    if (archive is None) == (supplied is None):
        raise Refusal("supply exactly one of --archive or --archive-sha256")
    if archive is not None:
        if not archive.is_file():
            raise Refusal(f"the archive {archive} is not a readable file")
        return sha256_file(archive)
    value = str(supplied)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise Refusal(f"--archive-sha256 {value!r} is not 64 lowercase hexadecimal characters")
    return value


def seal(receipt: dict[str, Any]) -> bytes:
    body = {key: value for key, value in receipt.items() if key != "record_sha256"}
    body["record_sha256"] = hashlib.sha256(canonical(body)).hexdigest()
    if tuple(sorted(body)) != tuple(sorted(RECEIPT_KEYS)):
        raise Refusal("the sealed receipt does not carry exactly the closed key set")
    return canonical(body)


def write_receipt(
    *,
    root: Path,
    state_home: Path,
    archive: Path | None,
    archive_sha256: str | None,
    operation_id: str | None,
    installed_at: str | None,
) -> Path:
    if not root.is_dir() or root.is_symlink():
        raise Refusal(f"the candidate root {root} is not an exact physical directory")
    absolute = Path(os.path.realpath(root))
    digest = resolve_archive_digest(archive, archive_sha256)
    if (absolute.name, absolute.parent.name, absolute.parent.parent.name) != (
        CANDIDATE_LEAF,
        digest,
        CANDIDATE_SEGMENTS[-1],
    ):
        raise Refusal(
            f"the candidate root {absolute} is not at {CANDIDATE_ROOT_LAYOUT} for this archive"
            f" digest; the verbs that admit this receipt resolve the root from that layout alone, so"
            " a receipt sealed elsewhere could never be admitted"
        )
    plan_sha256, digests = verify_root(absolute)
    journal_sha256 = hashlib.sha256(canonical({"verified": digests})).hexdigest()
    operation = operation_id or "op-" + hashlib.sha256(
        canonical({"archive_sha256": digest, "journal_sha256": journal_sha256})
    ).hexdigest()[:32]
    if not operation.startswith("op-") or len(operation) != 35 or any(
        character not in "0123456789abcdef" for character in operation[3:]
    ):
        raise Refusal(f"--operation-id {operation!r} is not the op-<32 lowercase hex> form")
    instant = installed_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not _UTC_INSTANT.match(instant):
        raise Refusal(f"--installed-at {instant!r} is not a YYYY-MM-DDTHH:MM:SSZ instant")
    receipt = {
        **RECEIPT_CONSTANTS,
        "archive_sha256": digest,
        "candidate_root_absolute_physical_path": os.fspath(absolute),
        "installed_at": instant,
        "journal_sha256": journal_sha256,
        "operation_id": operation,
        "plan_sha256": plan_sha256,
        "record_sha256": "",
    }
    body = seal(receipt)
    directory = state_home.joinpath(*RECEIPT_SEGMENTS)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.json"
    try:
        # O_NOFOLLOW does not exist on Windows, so it is applied only where the platform
        # defines it. It is reinforcement, not the control: with O_CREAT | O_EXCL the open
        # already fails EEXIST when the path names a symlink, even a dangling one, and this
        # receipt's documented threat model is drift detection, not a same-UID TOCTOU racer.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise Refusal(
            f"{path} already exists; this producer never replaces a sealed receipt, so remove the"
            " prior one deliberately or verify it instead"
        ) from exc
    except OSError as exc:
        raise Refusal(f"{path} could not be created: {exc}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        written = path.read_bytes()
    except OSError as exc:
        raise UnknownEffect(
            f"{path} was written but could not be read back to prove what it holds: {exc}"
        ) from exc
    if written != body:
        raise UnknownEffect(
            f"{path} holds {hashlib.sha256(written).hexdigest()} rather than the sealed"
            f" {hashlib.sha256(body).hexdigest()} this run wrote; the file is left in place because"
            " removing it would be a second effect, and it is not admissible evidence"
        )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seal one acquisition receipt over a verified candidate root")
    parser.add_argument("--root", type=Path, required=True, help=f"the candidate root, normally {CANDIDATE_ROOT_LAYOUT}")
    parser.add_argument("--state-home", type=Path, required=True, help=f"the XDG state home holding {RECEIPT_LAYOUT}")
    parser.add_argument("--archive", type=Path, default=None, help="digest this archive to name the receipt")
    parser.add_argument("--archive-sha256", default=None, help="the archive digest, when the archive is elsewhere")
    parser.add_argument("--operation-id", default=None)
    parser.add_argument("--installed-at", default=None, help="a YYYY-MM-DDTHH:MM:SSZ instant; defaults to now")
    arguments = parser.parse_args(argv)
    try:
        path = write_receipt(
            root=arguments.root,
            state_home=arguments.state_home,
            archive=arguments.archive,
            archive_sha256=arguments.archive_sha256,
            operation_id=arguments.operation_id,
            installed_at=arguments.installed_at,
        )
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED
    except UnknownEffect as unknown:
        print(f"effect unknown: {unknown}", file=sys.stderr)
        return EXIT_UNKNOWN
    print(f"receipt {path}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
