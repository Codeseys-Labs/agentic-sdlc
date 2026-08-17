#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Write the tracked RepositoryContractManifest at `.agentic-sdlc/repo.toml`.

ADR-0022 decision 2 mandates that file as the one public, tracked artifact inside the
otherwise private activation state root. `repository-contract.py` reads it and
`activation-planner.py` admits it, but nothing produced it: the ten required fields
existed only as a Python constant inside the reader, so an operator had to hand-author
the file from the reader's source. This module is the missing third half.

EVERY FIELD IS AN EXPLICIT INPUT. Nothing here infers, detects, or defaults a value.
That is a requirement, not a shortcut. Deriving `canonical_guidance` or `queue_adapter`
from the repository needs the greenfield/brownfield classifier, and no primary source
enumerates its "occupied surface" predicates -- issue 09, ADR-0022, and the activation
handoff all say "guidance, queue, decision, toolchain, hook or CI surface" without naming
a single path. The obvious guess is the harm: adopting `.github/workflows/` as the CI
predicate would classify every GitLab, Jenkins, and Buildkite repository as greenfield
and hand it a full proposed baseline, which ADR-0022 rejects by name. The classifier is
blocked pending an operator decision, so this module asks instead of guessing. `schema`
is an input too -- the operator states which contract version their intent is written
against, and any other value is refused rather than rewritten.

The reader owns the schema. `REQUIRED_FIELDS`, `MANIFEST_SCHEMA`, and `validate_contract`
are imported from it rather than restated, so a field added there cannot be silently
omitted here; `ORDERED_FIELDS` only fixes the emission ORDER and is asserted against the
reader's set at import. Every rendered manifest is parsed back and re-validated before a
byte reaches the filesystem, so this module cannot emit something the reader refuses.

Implementation Decision 10: the manifest is not ownership, tool, trust, route, or
readiness proof. The reader refuses by name any UNRECOGNIZED field whose name carries one
of those tokens, and this writer inherits that refusal instead of restating it. The command
line adds no way to spell such a field either, because every option is generated from the
reader's closed key set.

Field VALUES are NOT screened, and an earlier version of this paragraph wrongly concluded
from the option list that "the claim cannot be smuggled through argv". It can:
`--writing-profile "this manifest PROVES readiness, ownership, trust, tool identity and
route"` is accepted and the reader calls the result valid. Values are left unscreened
deliberately. Those tokens are ordinary English that legitimate intent needs -- an
`authoritative_gate` of `mise trust ./mise.toml && mise run check` contains "trust", a
`ci_expectation` naming a pinned toolchain contains "tool" -- so a value screen would refuse
true statements while a determined author just spells the claim another way; the reader
makes the same trade for the same reason when it screens only unrecognized NAMES. What does
hold is structural: names are what a machine consumer keys on, no consumer in this family
reads a claim out of a value, and every emitted manifest carries the header disclaimer
above the values. The residual is exactly that an operator can write a false sentence into
their own tracked intent file, and nothing here stops them.

Overwrite is refused without `--force`. A silent overwrite of tracked repository policy
is the worst thing this tool could do, so an existing manifest is a clean refusal before
any effect. `--force` replaces content IN PLACE through the already-verified descriptor:
no temporary sibling, no rename. That is deliberate. The state root's whitelist in
`activation-planner.py` is closed, so a strayed `.repo.toml.<pid>.tmp` left by a crash
would fail activation with `foreign-state` for reasons nobody could trace, while a
half-written manifest is simply refused as malformed by the reader and the engine. A
detectable bad state beats an untraceable one; the cost is that replacement is not atomic.

MODES ARE CLONEABLE, NOT PRIVATE. The engine admits this path under
`_assert_cloneable_private_node` rather than the strict exact-0700 rule precisely because
Git records no mode: a fresh clone materializes 0644 at umask 022 and 0664 at umask 002.
Creating the file 0600 would be inconsistent with a file whose purpose is to be committed,
so the file and the state root are created at the caller's umask. The one adjustment is
that an other-write bit is cleared from what this module creates, because at umask 000 the
umask-shaped result would be world-writable and the engine would then refuse the very file
this tool just wrote. Existing nodes are never re-moded -- they are refused, because
silently relaxing the mode of tracked repository policy is the writer's own version of a
silent overwrite.

Custody is fd-based. The target is the operator's own argument, opened `O_DIRECTORY` exactly
as the reader opens it; the state root and the manifest below it are opened `O_NOFOLLOW`, so
a symlinked parent cannot redirect custody, and `O_NONBLOCK`, matching the reader flag for
flag. `O_NONBLOCK` is load-bearing on the manifest: without it a FIFO planted at that path
blocks this module in `open(2)` forever -- on the shared-group checkout the next paragraph
documents, any group member can wedge it that way -- and it is also what makes the
regular-file guard reachable for the one non-regular type an unprivileged actor can plant.
The state root and the manifest must be caller-owned, non-symlink, of the
expected type, free of an extended ACL, single-linked (the manifest), and on the same
FILESYSTEM AND MOUNT as the target directory. That last pair is `st_dev` plus the Linux
mount id, the pair `activation-planner.py` binds: a bind mount planted over `.agentic-sdlc`
shares `st_dev` with the repository, so the mount id is the only check that sees it, and
without it this module wrote a manifest (exit 0, `valid` to the reader) that the engine then
refused as `foreign-state` -- while leaving it on disk.

The mount id is read from `/proc/self/fdinfo/<fd>`'s `mnt_id` on the already-verified
descriptor, so there is no second path lookup to swap; it is the same value the engine reads
through `statx(STATX_MNT_ID)`, measured equal on both the bound and the foreign mount. Two
residuals, stated exactly rather than as "matches the engine". On a non-Linux platform there
is no mount id and the comparison is skipped -- nothing is lost, because the engine declares
itself `unsupported` there and admits no manifest at all. And the engine additionally
requires that the whole absolute path from `/` to the target cross no mount boundary, which
refuses a target on any non-root filesystem; that is an engine-side platform limitation it
reports as `unsupported` rather than `foreign-state`, and this module does not pre-impose it.
So a written manifest is not a promise that the engine will admit the repository. It is the
narrower promise that this module did not create the `foreign-state` condition itself.

Group-write is permitted for the same reason the engine permits it, and carries the same
recorded exposure: on a shared-group checkout a group member can modify the manifest
afterwards.

This module runs no subprocess and never invokes Git, so it does not make the file
TRACKED. The reader deliberately does not verify trackedness either, and the engine
establishes the stronger property as a side effect of its cleanliness gate: the manifest is
visible to the Git projection, so an uncommitted manifest fails `_require_clean`. Staging
and committing the result stays an explicit operator step. Writing this file is also not
activation, not a gate, and not authorization for any outward effect.

Exit codes follow Implementation Decision 9: 0 written, 1 internal failure before any
effect, 2 grammar or schema, 3 clean refusal before any effect, 4 admitted PARTIAL or
UNKNOWN effect. The last one is not decorative, and both of its cases were wrong here
before: creating the state root is an effect, so a stop after it is 4 and never a "clean"
3, and a short write leaves a truncated manifest, so it is 4 and never a pre-effect 1.
`write_command` now DERIVES the code and the status from the effect the stop carries instead
of trusting each raise site, because trusting the raise sites is exactly how those two
drifted. `partial` is the one status that admits an effect; `refused` and `failed` are
pre-effect by construction.

One effect is avoided rather than reported. A target directory carrying a default ACL --
shared NFS, a setgid project directory -- hands every directory created under it an inherited
extended ACL, so the state root this module was about to create was refused immediately after
being created, leaving an ACL-poisoned directory behind. The inheritable ACL is therefore
checked BEFORE `mkdir`, which makes that whole realistic case a clean refusal with nothing
created. A post-`mkdir` stop is still NOT rolled back: `rmdir` resolves by NAME in a
directory another actor may be able to write, and a failed rollback would turn a known
partial effect into an unknown one, so the created directory is reported as the effect it is.

`activation-planner.py` maps custody refusals to 1 instead; that mapping predates the
decision, and the reader (`repository-contract.py`) is the contract this module follows. Its
code 4 spelling is the one this module does follow.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import os
import stat
import sys
import tomllib
from pathlib import Path
from typing import Any

READER_NAME = "repository-contract.py"


def _load_reader() -> Any:
    """Load the reader as the single definition of the schema it validates."""
    path = Path(__file__).resolve().with_name(READER_NAME)
    spec = importlib.util.spec_from_file_location("_agentic_sdlc_repository_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"canonical {READER_NAME} is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_reader = _load_reader()

MANIFEST_SCHEMA = _reader.MANIFEST_SCHEMA
REQUIRED_FIELDS = _reader.REQUIRED_FIELDS
STATE_DIRECTORY_NAME = _reader.STATE_DIRECTORY_NAME
REPO_MANIFEST_NAME = _reader.REPO_MANIFEST_NAME
MANIFEST_RELATIVE_PATH = _reader.MANIFEST_RELATIVE_PATH
canonical_bytes = _reader.canonical_bytes

RESULT_SCHEMA = "agentic-sdlc/repository-contract-write-result@1"

# Emission order only -- issue 09's reading order, so a reviewer diffing the manifest sees
# the fields in the order the contract text introduces them. The reader's REQUIRED_FIELDS
# remains the authority on WHICH fields exist, and the assertion below fails loudly at
# import if the two ever disagree rather than emitting a manifest missing a field.
ORDERED_FIELDS = (
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
)
if set(ORDERED_FIELDS) != set(REQUIRED_FIELDS):
    # A raise rather than an `assert`, which `python -O` strips: silently emitting a
    # manifest missing a field the reader requires is exactly the failure to prevent.
    raise RuntimeError("writer field order disagrees with the reader's schema")

HEADER = (
    "# RepositoryContractManifest -- portable repository intent (ADR-0022 decision 2).\n"
    "# Tracked on purpose. Every value is an explicit operator statement, never a detected fact.\n"
    "# Not proof of ownership, tool identity, trust, route, or readiness: those live in the\n"
    "# machine-local receipt plane, and readiness is a separate assessment.\n"
)

# Implementation Decision 9.
INTERNAL_CODE = 1
SCHEMA_CODE = _reader.SCHEMA_CODE
REFUSAL_CODE = _reader.CUSTODY_CODE
EFFECT_CODE = 4

_ACL_ATTRIBUTES = ("system.posix_acl_access", "system.posix_acl_default", "system.nfs4_acl")
# The subset a CREATED directory inherits from its parent, checked before the mkdir.
_INHERITABLE_ACL_ATTRIBUTES = ("system.posix_acl_default", "system.nfs4_acl")


class WriteError(Exception):
    """A stop carrying the status, the reason, the exit code, and the effect so far."""

    def __init__(self, status: str, reason: str, code: int, effect: str = "none") -> None:
        super().__init__(reason)
        self.status, self.reason, self.code, self.effect = status, reason, code, effect


def build_contract(values: Any) -> dict[str, Any]:
    """Validate operator input against the READER's schema, not a restatement of it."""
    try:
        return _reader.validate_contract(values)
    except _reader.ContractError as exc:
        raise WriteError(exc.status, exc.reason, exc.code) from exc


def _escape(value: str, label: str) -> str:
    """Escape a TOML basic string. Control characters must not appear literally."""
    known = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}
    out: list[str] = []
    for character in value:
        if character in known:
            out.append(known[character])
        elif ord(character) < 0x20 or ord(character) == 0x7F:
            out.append(f"\\u{ord(character):04X}")
        else:
            out.append(character)
    rendered = "".join(out)
    try:
        rendered.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WriteError("refused", f"invalid {label}", SCHEMA_CODE) from exc
    return rendered


def render_manifest(contract: dict[str, Any]) -> bytes:
    """Render the manifest and prove the reader accepts it before anything is written."""
    body = "".join(f'{name} = "{_escape(contract[name], name)}"\n' for name in ORDERED_FIELDS)
    payload = (HEADER + "\n" + body).encode("utf-8")
    try:
        reparsed = _reader.parse_contract(payload)
    except _reader.ContractError as exc:
        raise WriteError("failed", f"rendered manifest is not readable: {exc.reason}", INTERNAL_CODE) from exc
    if reparsed != contract:
        raise WriteError("failed", "rendered manifest does not round-trip", INTERNAL_CODE)
    return payload


def _extended_attributes(fd: int) -> tuple[str, ...]:
    """Extended attribute names on the descriptor; empty only where none can exist at all.

    ENOTSUP is the one tolerated failure, because it means this filesystem cannot carry an ACL
    and there is nothing to refuse. Every other failure refuses: for an ACL predicate a
    swallowed EACCES fails OPEN.
    """
    try:
        return tuple(os.listxattr(fd))
    except OSError as exc:
        if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
            return ()
        raise WriteError("refused", "cannot read ACL state", REFUSAL_CODE) from exc


def _has_extended_acl(fd: int) -> None:
    """Refuse an extended ACL, the fail-closed half of permitting group-write.

    Group bits double as the POSIX.1e mask, so a mode-only rule cannot tell the caller's
    umask apart from a write grant to a named user. The engine refuses these nodes, so
    writing into one would produce a manifest the engine will not admit.
    """
    attributes = _extended_attributes(fd)
    if any(name in attributes for name in _ACL_ATTRIBUTES):
        raise WriteError("refused", "unsafe ACL state", REFUSAL_CODE)


def _assert_no_inheritable_acl(target_fd: int) -> None:
    """Refuse BEFORE `mkdir` when the created state root would inherit an extended ACL.

    A default ACL on the repository root is inherited by every directory created beneath it,
    so the state root this module is about to create would carry `posix_acl_default` and
    `posix_acl_access` and be refused -- by the engine, and by `_has_extended_acl` here --
    immediately AFTER the mkdir. That turned a realistic environment into an admitted effect
    plus an ACL-poisoned leftover directory. Checked here, it is a clean refusal with nothing
    created. An NFSv4 ACL counts for the same reason it does below: it is inheritable and the
    POSIX mask coupling does not hold on such a mount.

    The repository root's own ACL is not otherwise this module's business, so this runs only
    on the create path: an already-existing clean state root beneath an ACL-bearing root is
    written normally.
    """
    attributes = _extended_attributes(target_fd)
    if any(name in attributes for name in _INHERITABLE_ACL_ATTRIBUTES):
        raise WriteError("refused", f"cannot create {STATE_DIRECTORY_NAME}: inheritable ACL state", REFUSAL_CODE)


def _mount_id(fd: int) -> int | None:
    """The mount this descriptor lives on, or None where the platform has no mount ids.

    Read from `/proc/self/fdinfo/<fd>` on the already-verified descriptor rather than by a
    second path lookup, and measured equal to the `statx(STATX_MNT_ID)` value
    `activation-planner.py` binds. None ONLY on a non-Linux platform, where the engine is
    itself `unsupported` and admits nothing; an unreadable fdinfo on Linux is a refusal,
    because a mount identity this module cannot read is one it cannot compare.
    """
    if sys.platform != "linux":
        return None
    try:
        with open(f"/proc/self/fdinfo/{fd}", "rb") as handle:
            raw = handle.read().decode("utf-8", "strict")
    except (OSError, UnicodeError) as exc:
        raise WriteError("refused", "cannot read mount identity", REFUSAL_CODE) from exc
    for line in raw.splitlines():
        if line.startswith("mnt_id:"):
            try:
                return int(line.split(":", 1)[1])
            except ValueError as exc:
                raise WriteError("refused", "unreadable mount identity", REFUSAL_CODE) from exc
    raise WriteError("refused", "mount identity is unavailable", REFUSAL_CODE)


def _node_identity(fd: int) -> tuple[int, int | None]:
    """The `(st_dev, mount id)` pair the engine binds from the target directory."""
    return os.fstat(fd).st_dev, _mount_id(fd)


def _assert_bound_mount(fd: int, root: tuple[int, int | None], label: str) -> None:
    """Refuse a node the engine would call `foreign-state` for sitting off the bound mount."""
    if _node_identity(fd) != root:
        raise WriteError("refused", f"unsafe {label}", REFUSAL_CODE)


def _clear_other_write(fd: int, mode: int) -> int:
    """Keep what this module creates admissible at every umask, including 000."""
    if mode & 0o002:
        mode &= ~0o002
        os.fchmod(fd, mode)
    return mode


def _open_target(target: Path) -> int:
    try:
        return os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except FileNotFoundError:
        raise WriteError("refused", "target does not exist", REFUSAL_CODE) from None
    except OSError as exc:
        raise WriteError("refused", "cannot open target", REFUSAL_CODE) from exc


def _open_state_root(target_fd: int, root: tuple[int, int | None]) -> tuple[int, str]:
    """Open the state root, creating it at the caller's umask when it is absent."""
    # O_NONBLOCK for flag-for-flag parity with the reader. O_DIRECTORY already refuses a FIFO
    # here with ENOTDIR, so unlike the manifest below this one cannot hang; parity is cheaper
    # to keep than to re-derive every time someone compares the two modules.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    effect = "none"
    try:
        state_fd = os.open(STATE_DIRECTORY_NAME, flags, dir_fd=target_fd)
    except FileNotFoundError:
        _assert_no_inheritable_acl(target_fd)
        try:
            os.mkdir(STATE_DIRECTORY_NAME, 0o777, dir_fd=target_fd)
        except OSError as exc:
            raise WriteError("refused", f"cannot create {STATE_DIRECTORY_NAME}", REFUSAL_CODE) from exc
        effect = "state-root-created"
        try:
            state_fd = os.open(STATE_DIRECTORY_NAME, flags, dir_fd=target_fd)
        except OSError as exc:
            raise WriteError("failed", f"cannot open {STATE_DIRECTORY_NAME}", INTERNAL_CODE, effect) from exc
    except OSError as exc:
        raise WriteError("refused", f"unsafe {STATE_DIRECTORY_NAME}", REFUSAL_CODE) from exc
    try:
        info = os.fstat(state_fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise WriteError("refused", f"unsafe {STATE_DIRECTORY_NAME}", REFUSAL_CODE, effect)
        mode = stat.S_IMODE(info.st_mode)
        if effect == "state-root-created":
            mode = _clear_other_write(state_fd, mode)
        if mode & 0o002:
            raise WriteError("refused", f"unsafe {STATE_DIRECTORY_NAME}", REFUSAL_CODE, effect)
        _has_extended_acl(state_fd)
        # The engine's remaining custody predicate: same filesystem AND same mount as the
        # target, which is what refuses a bind mount planted over `.agentic-sdlc`.
        _assert_bound_mount(state_fd, root, STATE_DIRECTORY_NAME)
    except OSError as exc:
        # `fchmod` on a directory this module just created is the reachable one. An unhandled
        # OSError would escape `write_command` entirely -- no result document, no exit code
        # from Decision 9 -- while the created state root stayed on disk, so it is reported as
        # a failure carrying whatever effect has happened so far.
        os.close(state_fd)
        raise WriteError("failed", f"cannot secure {STATE_DIRECTORY_NAME}", INTERNAL_CODE, effect) from exc
    except BaseException as exc:
        os.close(state_fd)
        if isinstance(exc, WriteError):
            exc.effect = effect if exc.effect == "none" else exc.effect
        raise
    return state_fd, effect


def _open_manifest(state_fd: int, root: tuple[int, int | None], *, force: bool, effect: str) -> int:
    """Create the manifest, or open an existing one for in-place replacement."""
    # O_NONBLOCK matches the reader and is load-bearing, not cosmetic: a FIFO planted at this
    # path -- which any member of a shared group can do on the checkout this module's custody
    # documents -- otherwise blocks the force branch in open(2) forever, and it is what makes
    # the S_ISREG guard below reachable for the one non-regular type an unprivileged actor can
    # plant. It changes nothing about writing to a regular file, which is all this module does.
    flags = os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        manifest_fd = os.open(REPO_MANIFEST_NAME, flags | os.O_CREAT | os.O_EXCL, 0o666, dir_fd=state_fd)
    except FileExistsError:
        if not force:
            raise WriteError("refused", f"{MANIFEST_RELATIVE_PATH} already exists; pass --force to replace it", REFUSAL_CODE, effect) from None
        try:
            manifest_fd = os.open(REPO_MANIFEST_NAME, flags, dir_fd=state_fd)
        except OSError as exc:
            raise WriteError("refused", f"unsafe {MANIFEST_RELATIVE_PATH}", REFUSAL_CODE, effect) from exc
        try:
            info = os.fstat(manifest_fd)
            # Match the reader and the engine exactly: a foreign-owned, multiply-linked,
            # other-writable, non-regular, or ACL-bearing manifest is refused rather than
            # rewritten. Replacing content through a second hard link would also mutate a
            # file outside the state root.
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o002:
                raise WriteError("refused", f"unsafe {MANIFEST_RELATIVE_PATH}", REFUSAL_CODE, effect)
            _has_extended_acl(manifest_fd)
            # An existing node can be a bind mount over the manifest, so its mount is checked
            # too. A node this module CREATES lands in the already-verified state root by
            # `dir_fd`, so it inherits that directory's mount and needs no separate check.
            _assert_bound_mount(manifest_fd, root, MANIFEST_RELATIVE_PATH)
        except BaseException as exc:
            os.close(manifest_fd)
            if isinstance(exc, WriteError) and exc.effect == "none":
                exc.effect = effect
            raise
        return manifest_fd
    except OSError as exc:
        raise WriteError("refused", f"unsafe {MANIFEST_RELATIVE_PATH}", REFUSAL_CODE, effect) from exc
    try:
        _clear_other_write(manifest_fd, stat.S_IMODE(os.fstat(manifest_fd).st_mode))
    except OSError as exc:
        # The manifest now EXISTS and is empty, which the reader refuses as malformed. An
        # unhandled OSError here would leave that behind while crashing without a result
        # document at all, so it is reported as the admitted effect it is.
        os.close(manifest_fd)
        raise WriteError("failed", f"cannot mode {MANIFEST_RELATIVE_PATH}", EFFECT_CODE, "manifest-unknown") from exc
    except BaseException:
        os.close(manifest_fd)
        raise
    return manifest_fd


def emit(target: Path, payload: bytes, *, force: bool) -> str:
    """Place the bytes. Every refusal happens before the first byte is written."""
    target_fd = _open_target(target)
    try:
        root = _node_identity(target_fd)
        state_fd, effect = _open_state_root(target_fd, root)
        try:
            manifest_fd = _open_manifest(state_fd, root, force=force, effect=effect)
            try:
                # From here the effect is real: a failure leaves a truncated manifest, which
                # the reader and the engine refuse as malformed. Implementation Decision 9
                # calls that an admitted UNKNOWN effect -- code 4. Never a clean refusal, and
                # never a pre-effect internal failure either: a short write reported 1 here
                # while admitting `manifest-unknown` in the same result document.
                os.ftruncate(manifest_fd, 0)
                written = os.write(manifest_fd, payload)
                if written != len(payload):
                    raise WriteError("failed", f"partial write of {MANIFEST_RELATIVE_PATH}", EFFECT_CODE, "manifest-unknown")
                os.fsync(manifest_fd)
            except OSError as exc:
                raise WriteError("failed", f"cannot write {MANIFEST_RELATIVE_PATH}", EFFECT_CODE, "manifest-unknown") from exc
            finally:
                os.close(manifest_fd)
            try:
                os.fsync(state_fd)
            except OSError as exc:
                raise WriteError("failed", f"cannot persist {STATE_DIRECTORY_NAME}", EFFECT_CODE, "manifest-unknown") from exc
        finally:
            os.close(state_fd)
    finally:
        os.close(target_fd)
    return "manifest-written"


def _result(status: str, target: Path, *, effect: str, code: int, contract: dict[str, Any] | None = None, sha256: str | None = None, reasons: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "command": "write",
        "status": status,
        "effect": effect,
        "exit_code": code,
        "target": str(target),
        "path": MANIFEST_RELATIVE_PATH,
        "manifest_sha256": sha256,
        "contract": contract,
        "reasons": reasons or [],
    }


def write_command(target: Path, values: Any, *, force: bool = False) -> tuple[dict[str, Any], int]:
    """Write the manifest from fully explicit input. No field is inferred or defaulted."""
    target = Path(target)
    try:
        if not target.is_absolute():
            raise WriteError("refused", "target must be an absolute path", REFUSAL_CODE)
        contract = build_contract(values)
        payload = render_manifest(contract)
        effect = emit(target, payload, force=force)
        return _result("written", target, effect=effect, code=0, contract=contract, sha256=hashlib.sha256(payload).hexdigest()), 0
    except WriteError as exc:
        # Implementation Decision 9 DERIVED from the admitted effect rather than trusted per
        # raise site. Exit 3 means "clean refusal before any effect" and 1 means "internal
        # failure before any effect", so a stop that carries an effect can be neither; it is
        # 4, with the one status that admits an effect. Both violations were reachable here,
        # and each raise site individually looked plausible, which is why this is a single
        # invariant at the boundary instead of a rule each site must remember.
        status, code = ("partial", EFFECT_CODE) if exc.effect != "none" else (exc.status, exc.code)
        return _result(status, target, effect=exc.effect, code=code, reasons=[exc.reason]), code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the tracked repository contract manifest.")
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", description="Every field is an explicit input; nothing is inferred or defaulted.")
    write.add_argument("--target", type=Path, required=True, help="absolute path of the repository root")
    write.add_argument("--force", action="store_true", help="replace an existing manifest instead of refusing")
    for name in ORDERED_FIELDS:
        help_text = f"must be {MANIFEST_SCHEMA}" if name == "schema" else f"explicit {name.replace('_', ' ')}"
        write.add_argument(f"--{name.replace('_', '-')}", dest=name, required=True, help=help_text)
    args = parser.parse_args(argv)
    result, code = write_command(args.target, {name: getattr(args, name) for name in ORDERED_FIELDS}, force=args.force)
    sys.stdout.buffer.write(canonical_bytes(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
