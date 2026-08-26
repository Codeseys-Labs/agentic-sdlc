"""The ONE reader of `.git` metadata this bundle carries. No `git` process is ever spawned.

WHY IT LIVES HERE, in the skill payload, and not under `scripts/`. It has two consumers on two
different planes: `offline-inspect.py`, which is INSTALLED into an operator's home as part of this
skill, and the receipted lifecycle verbs under `scripts/`, which are not installed anywhere. A
module under `scripts/` would be unreachable from a copy-mode skill install -- the installed tree
holds `skills/`, `agents/`, `commands/`, `workflows/`, and `hooks/` and nothing else -- so the only
location that survives BOTH planes is inside the skill's own payload, where `offline-inspect.py`
finds it as a plain sibling and a distribution's `scripts/` finds it at a fixed relative path from
the distribution root. `skills/model-tier-rightsizing/scripts/` already ships underscore-named
importable modules beside hyphen-named tools for the same reason; this file follows that shape.

WHAT IT REPLACED. Two independent readers of the same metadata existed: `offline-inspect.py`'s three
shape checkers (a `.git` directory must hold a regular one-line `HEAD` plus `objects/` and `refs/`
under its commondir; a `.git` file must be exactly one `gitdir: ` line) and
`ccodex_sdlc_uninstall.py`'s proven trio (`git_metadata_directory`, `observe_dirty`,
`observe_commit`). The trio is the substrate here and the shape checkers are the admission gate on
top of it, because the two answer different questions about one subject: "where does this root's
metadata live" versus "is this metadata a git project this lifecycle may publish into".

ACCESS TIMES ARE PRESERVED, STRICTLY, and that decides the fail-direction of everything below.
Every metadata read goes through `read_without_atime`, which opens with `O_NOATIME | O_NOFOLLOW` and
raises `MetadataUnreadable` rather than retrying without it. That is `offline-inspect.py`'s own
contract -- it is a read-only observer whose test suite measures `st_atime_ns` before and after -- and
a fallback here would quietly break it on exactly the hosts where the guarantee is hardest to keep.
The consequence for the other consumer is stated rather than hidden: `O_NOATIME` needs the file's
owner (or `CAP_FOWNER`), so metadata this process does not own reads as unreadable, `observe_dirty`
answers `True`, and `observe_commit` answers `unknown`. Both of those are the fail-direction those
functions already document -- a receipt that cannot read a tree may not assert the tree equals a
commit -- and the receipted project plane is certified on Linux only, where the flag exists.

WORKTREE CONTENT is a different subject and is read plainly (`_blob_sha1`): hashing tracked payload
is what `observe_dirty` is for, the file is the operator's own, and no caller of this module claims
to leave a worktree's access times untouched. Only METADATA carries the guarantee.

This module reads. It never writes, never spawns, never networks, and never decides an
authorization: a verdict here is an observation about bytes on disk, and every consumer names it in
its own vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import stat
import struct

#: The four verdicts `admit` can return. They are FINER than either consumer's own vocabulary on
#: purpose: `offline-inspect.py` renders `absent` as `create` and reports `unsafe-node` and
#: `invalid-git-metadata` separately, while the lifecycle ladder maps `absent` onto
#: `not-a-git-project` and both refusals onto `unsafe-node`. A module that answered in one
#: consumer's tokens would force the other to translate back through a guess.
ABSENT = "absent"
ADMITTED = "admitted"
UNSAFE_NODE = "unsafe-node"
INVALID_METADATA = "invalid-git-metadata"

#: A `.git` file is one short line. The cap is what keeps a hostile or corrupt node from being read
#: into memory before its shape is judged.
MAX_GIT_FILE_BYTES = 4096
#: `HEAD` holds either 40 hex characters (sha1) or 64 (sha256), so both lengths are admitted.
_COMMIT_LENGTHS = (40, 64)
_HEX = "0123456789abcdefABCDEF"
#: The explicit value `observe_commit` returns when no commit can be read. A plausible-looking
#: substitute would be a claim; this is a statement the receipt family admits.
COMMIT_UNKNOWN = "unknown"
#: The three index entry modes `observe_dirty` compares. A gitlink (0o160000) and a sparse-directory
#: entry are deliberately absent: neither can be compared by hashing one worktree node, so both
#: answer dirty.
_GIT_MODE_FILE = 0o100644
_GIT_MODE_EXECUTABLE = 0o100755
_GIT_MODE_SYMLINK = 0o120000
_GIT_MODES = (_GIT_MODE_FILE, _GIT_MODE_EXECUTABLE, _GIT_MODE_SYMLINK)


#: The two KINDS of read failure, kept apart because a consumer renders them differently: a host or
#: an owner that cannot grant an atime-free read is a capability statement, and everything else is an
#: ordinary unreadable file. `offline-inspect.py` reports these two tokens verbatim as its own refusal
#: reasons, which is why they are spelled in its vocabulary rather than in prose here.
NO_ATIME = "no-atime-unavailable"
UNREADABLE = "unreadable"


class MetadataUnreadable(Exception):
    """One file could not be read without disturbing its access time.

    `reason` is a short phrase a caller may put in front of an operator, never a stack trace. `kind`
    is one of `NO_ATIME` or `UNREADABLE`, so a caller can distinguish "this host will not let me read
    without a side effect" from "this file will not read" without matching on the prose.
    """

    def __init__(self, reason: str, kind: str = UNREADABLE) -> None:
        super().__init__(reason)
        self.reason = reason
        self.kind = kind


@dataclass(frozen=True)
class Admission:
    """One root's git-project verdict, plus the metadata directory it was decided from.

    `metadata` is populated only for `ADMITTED`: a refusal has nothing a caller may go on to read,
    and handing back a directory beside a refusal is how a caller ends up using it anyway.
    """

    verdict: str
    #: Why, in one phrase. Empty for `ADMITTED` and for `ABSENT`, which need no explanation.
    reason: str = ""
    metadata: Path | None = None

    @property
    def admitted(self) -> bool:
        return self.verdict == ADMITTED


def read_without_atime(path: Path, limit: int | None = None) -> bytes:
    """Read one file without updating its access time, or raise `MetadataUnreadable`.

    `O_NOFOLLOW` is part of the same guarantee: a path replaced by a symlink is refused rather than
    followed to whatever it names, and `O_NOATIME` is never dropped as a retry -- see this module's
    docstring for why the strictness is the point rather than an inconvenience.

    It reads more than git metadata: `offline-inspect.py` reads the instruction files it previews
    through this same function, because "observe without leaving a trace" is one property and a
    second copy of it would be a second thing to keep true.
    """
    noatime = getattr(os, "O_NOATIME", None)
    if noatime is None:
        raise MetadataUnreadable(
            "this platform cannot read a file without updating its access time (no O_NOATIME)",
            NO_ATIME,
        )
    flags = os.O_RDONLY | noatime | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.EACCES, errno.EOPNOTSUPP, errno.ENOTSUP):
            raise MetadataUnreadable(
                f"{path.name!r} could not be read without updating its access time"
                f" ({errno.errorcode.get(exc.errno, exc.errno)})",
                NO_ATIME,
            ) from exc
        raise MetadataUnreadable(
            f"{path.name!r} could not be opened ({exc.strerror or exc.__class__.__name__})"
        ) from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise MetadataUnreadable(f"{path.name!r} is not a regular file")
        chunks: list[bytes] = []
        read = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
            read += len(chunk)
            if limit is not None and read > limit:
                break
        raw = b"".join(chunks)
        return raw if limit is None else raw[:limit]
    except OSError as exc:
        raise MetadataUnreadable(
            f"{path.name!r} could not be read ({exc.strerror or exc.__class__.__name__})"
        ) from exc
    finally:
        os.close(descriptor)


def node_mode(path: Path) -> int | None:
    """The path's own `st_mode`, `None` when it is absent, raising for any other stat failure.

    `lstat`, never `stat`: the question every caller here asks is what the node IS, and a symlink
    that resolved to a directory would answer a question nobody asked.
    """
    try:
        return path.lstat().st_mode
    except FileNotFoundError:
        return None


def one_line(raw: bytes) -> str | None:
    """The single line this metadata file holds, or `None` when it is not exactly one clean line."""
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return None
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or "\x00" in lines[0]:
        return None
    return lines[0]


def valid_head(metadata: Path) -> bool:
    """Whether `<metadata>/HEAD` is one line naming either a ref under `refs/` or a raw commit."""
    try:
        raw = read_without_atime(metadata / "HEAD")
    except MetadataUnreadable:
        return False
    value = one_line(raw)
    if value is None:
        return False
    if value.startswith("ref: refs/"):
        return len(value) > len("ref: refs/") and not value.endswith("/")
    return len(value) in _COMMIT_LENGTHS and all(character in _HEX for character in value)


def common_directory(metadata: Path) -> Path | None:
    """The shared object/ref storage a linked worktree's metadata points at, or `None`.

    A linked worktree's own metadata directory holds `HEAD` and `commondir` but no `objects/` or
    `refs/` of its own, so the structural check has to look where `commondir` says.
    """
    commondir = metadata / "commondir"
    mode = node_mode(commondir)
    if mode is None or not stat.S_ISREG(mode):
        return None
    try:
        raw = read_without_atime(commondir)
    except MetadataUnreadable:
        return None
    value = one_line(raw)
    if value is None:
        return None
    common = Path(value)
    return common if common.is_absolute() else metadata / common


def metadata_directory_admits(metadata: Path) -> bool:
    """Whether one metadata DIRECTORY has the minimum structure of a git project.

    A regular one-line `HEAD` plus `objects/` and `refs/` directories under whatever `commondir`
    names. Nothing here parses a config, reads a ref, or judges whether the repository is useful:
    the question is only whether this is git metadata rather than a directory that happens to be
    called `.git`.
    """
    mode = node_mode(metadata)
    if mode is None or not stat.S_ISDIR(mode):
        return False
    head_mode = node_mode(metadata / "HEAD")
    if head_mode is None or not stat.S_ISREG(head_mode) or not valid_head(metadata):
        return False
    common = common_directory(metadata)
    storage = common if common is not None else metadata
    objects_mode = node_mode(storage / "objects")
    refs_mode = node_mode(storage / "refs")
    if objects_mode is None or not stat.S_ISDIR(objects_mode):
        return False
    return refs_mode is not None and stat.S_ISDIR(refs_mode)


def gitfile_target(root: Path, gitfile: Path) -> Path | None:
    """The metadata directory a `.git` FILE names, or `None` when it is not exactly one `gitdir:` line.

    A relative target resolves against the root that holds the `.git` file, which is what git itself
    does and what makes a linked worktree readable without a subprocess.
    """
    try:
        raw = read_without_atime(gitfile, MAX_GIT_FILE_BYTES)
    except MetadataUnreadable:
        return None
    value = one_line(raw)
    if value is None or not value.startswith("gitdir: "):
        return None
    target = value[len("gitdir: ") :]
    if not target:
        return None
    gitdir = Path(target)
    return gitdir if gitdir.is_absolute() else root / gitdir


def metadata_directory(root: Path) -> Path | None:
    """Where this root's git metadata lives, following one level of `gitdir:` indirection, or `None`.

    This is the trio's original question and it is deliberately structure-free: it answers where to
    look, not whether what is there admits. `admit` is the gate; this is the locator every observer
    below shares, and a caller that needs both asks `admit` and reads its `metadata`.
    """
    node = root / ".git"
    mode = node_mode(node)
    if mode is None:
        return None
    if stat.S_ISREG(mode):
        target = gitfile_target(root, node)
        if target is None:
            return None
        node = target
    elif not stat.S_ISDIR(mode):
        return None
    return node if node.is_dir() else None


def admit(root: Path) -> Admission:
    """Decide whether one directory is a git project this lifecycle may treat as a root.

    The four verdicts, and what separates them:

      * `ABSENT` -- there is no `.git` entry at all, or the candidate is not a directory. Nothing is
        wrong with the node; there is simply no project here.
      * `UNSAFE_NODE` -- `.git` exists and is neither a regular file nor a directory. A symlink, a
        fifo, a socket, or a device node is refused by NODE TYPE, before anything is read out of it.
      * `INVALID_METADATA` -- the node type is admissible and the metadata does not hold up: a
        `.git` file that is not exactly one `gitdir: ` line, a target that is not a directory, or a
        directory missing its one-line `HEAD`, `objects/`, or `refs/`.
      * `ADMITTED` -- with the metadata directory it was decided from.

    A LINKED WORKTREE ADMITS, and it admits as ITSELF: the root is the directory holding the `.git`
    file, never the primary checkout its `gitdir:` names. Two linked worktrees of one repository are
    therefore two roots, which is the intended semantics wherever a root is a key.
    """
    root_mode = node_mode(root)
    if root_mode is None or not stat.S_ISDIR(root_mode):
        return Admission(ABSENT)
    node = root / ".git"
    mode = node_mode(node)
    if mode is None:
        return Admission(ABSENT)
    if stat.S_ISDIR(mode):
        if metadata_directory_admits(node):
            return Admission(ADMITTED, metadata=node)
        return Admission(
            INVALID_METADATA,
            "its .git directory holds no readable one-line HEAD with objects/ and refs/ under its"
            " commondir",
        )
    if stat.S_ISREG(mode):
        target = gitfile_target(root, node)
        if target is None:
            return Admission(
                INVALID_METADATA, "its .git file is not exactly one readable 'gitdir: <path>' line"
            )
        if metadata_directory_admits(target):
            return Admission(ADMITTED, metadata=target)
        return Admission(
            INVALID_METADATA,
            f"its .git file names {str(target)!r}, which is not a readable git metadata directory",
        )
    return Admission(
        UNSAFE_NODE,
        "its .git is neither a regular file nor a directory, so it is reported rather than read",
    )


def walk_up(start: Path) -> Path | None:
    """The nearest ancestor of `start` (inclusive) holding a `.git` entry of any shape, or `None`.

    PRESENCE, not admission: the walk stops at the first `.git` it can see and `admit` then judges
    it. Walking PAST a `.git` that fails to admit would silently activate a parent repository for an
    operator standing inside a broken one, which is the guess this ladder exists to remove.
    """
    current = start
    while True:
        if node_mode(current / ".git") is not None:
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def observe_commit(root: Path) -> str:
    """This root's own commit, read from git metadata, or the explicit `COMMIT_UNKNOWN`.

    No `git` process is spawned, ever: a lifecycle verb that shelled out to resolve a commit would
    make an ambient executable part of what a receipt asserts. One level of loose-ref indirection is
    followed; a packed ref, an unreadable file, or any other shape answers `unknown`, which is a
    statement the receipt family admits rather than a plausible-looking value.
    """
    metadata = metadata_directory(root)
    if metadata is None:
        return COMMIT_UNKNOWN
    try:
        head = read_without_atime(metadata / "HEAD", MAX_GIT_FILE_BYTES).decode("utf-8", "replace").strip()
        if _is_commit(head):
            return head
        if not head.startswith("ref:"):
            return COMMIT_UNKNOWN
        reference = head.split(":", 1)[1].strip()
        if not reference or ".." in reference.split("/"):
            return COMMIT_UNKNOWN
        resolved = (
            read_without_atime(metadata / reference, MAX_GIT_FILE_BYTES).decode("utf-8", "replace").strip()
        )
        return resolved if _is_commit(resolved) else COMMIT_UNKNOWN
    except (MetadataUnreadable, OSError, ValueError):
        return COMMIT_UNKNOWN


def _is_commit(value: str) -> bool:
    return len(value) in _COMMIT_LENGTHS and all(character in _HEX for character in value)


def _index_entries(raw: bytes) -> tuple[list[dict[str, object]], bool]:
    """Parse a git index (version 2 or 3) into its entries plus its cache-tree validity.

    THE INDEX IS THE ONLY THING READ, and that is the whole design: every entry records the blob's
    own sha1 beside the path, so a worktree can be compared against it by re-hashing content -- no
    object store, no pack index, no delta chains, and no `git` process. Version 4 uses
    prefix-compressed path names and is deliberately NOT parsed: a half-understood index would answer
    with confidence about entries it misread, so an unsupported version raises and the caller answers
    `dirty`.
    """
    if raw[:4] != b"DIRC" or len(raw) < 32:
        raise ValueError("not a DIRC index")
    version, count = struct.unpack(">II", raw[4:12])
    if version not in (2, 3):
        raise ValueError(f"index version {version} is not parsed here")
    offset = 12
    entries: list[dict[str, object]] = []
    for _ in range(count):
        start = offset
        fields = struct.unpack(">10I", raw[offset : offset + 40])
        sha = raw[offset + 40 : offset + 60].hex()
        flags, = struct.unpack(">H", raw[offset + 60 : offset + 62])
        offset += 62
        extended_flags = 0
        if flags & 0x4000:
            extended_flags, = struct.unpack(">H", raw[offset : offset + 2])
            offset += 2
        length = flags & 0x0FFF
        if length < 0x0FFF:
            name = raw[offset : offset + length]
            offset += length
        else:
            end = raw.index(b"\0", offset)
            name = raw[offset:end]
            offset = end
        offset += 1
        while (offset - start) % 8:
            offset += 1
        entries.append(
            {
                "name": name.decode("utf-8", "replace"),
                "sha1": sha,
                "mode": fields[6],
                "stage": (flags >> 12) & 0x3,
                "extended_flags": extended_flags,
            }
        )
    # The extensions, then the 20-byte trailer checksum. Only `TREE` is read, and only its ROOT row:
    # git invalidates a cache-tree row (entry_count < 0) when the index below it is staged, so an
    # invalid root is the witness that the index no longer agrees with a written tree.
    tail = raw[offset:-20]
    root_valid = False
    position = 0
    while position + 8 <= len(tail):
        signature = tail[position : position + 4]
        size, = struct.unpack(">I", tail[position + 4 : position + 8])
        position += 8
        payload = tail[position : position + size]
        position += size
        if signature == b"TREE" and payload:
            separator = payload.index(b"\0")
            newline = payload.index(b"\n", separator)
            root_valid = int(payload[separator + 1 : newline].split(b" ")[0]) >= 0
    return entries, root_valid


def _blob_sha1(path: Path, mode: int) -> str:
    """Git's own blob identity for one worktree node: sha1 over `blob <len>\\0` plus the content."""
    data = os.readlink(path).encode("utf-8") if mode == _GIT_MODE_SYMLINK else path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def observe_dirty(root: Path) -> tuple[bool, str]:
    """Whether this tree may still be asserted equal to the commit `observe_commit` names --
    computed, with its residuals stated, rather than assumed.

    WHAT `dirty: False` ASSERTS, exactly: every path the git index tracks exists in the worktree with
    the node type and executable bit the index records and hashes to the blob the index records, no
    entry is conflicted, and the index's own cache-tree root is intact. That last condition is what
    catches the common `git add`-without-commit: git invalidates the cache-tree row when the index is
    staged, and without it a staged change would read as clean because the worktree and the index
    agree with each other while both differ from the commit. Measured in both directions on
    2026-08-25 in a throwaway repository: a clean tree, a content-identical rewrite that only moved
    mtime, a modified file, a deleted tracked file, a staged-not-committed change, and the commit
    that follows it.

    TWO RESIDUALS, NAMED because a `False` here is a claim in sealed evidence:

      * UNTRACKED CONTENT IS NOT INSPECTED. Deciding whether an untracked path is ignored needs the
        full `.gitignore` semantics, which this module will not reimplement, so an untracked file
        beside a tracked payload does not move this flag. `dirty: False` therefore means "no tracked
        path differs", not "no other file exists".
      * NO OBJECT STORE IS READ. The commit's own tree is never fetched, because reaching a packed
        object means a pack index and delta chains, and a detector that answered only for loose
        objects would give two hosts different answers about one tree. So a deliberate
        index-versus-commit surgery (`git reset --soft`, `git update-index`) that leaves the
        cache-tree intact is not detected.

    Everything unreadable, unsupported, or unparseable answers `True`: this flag fails toward "not
    asserted", which is the direction that cannot make a receipt claim more than it observed.
    """
    metadata = metadata_directory(root)
    if metadata is None:
        return True, "no readable git metadata, so nothing here can be compared with a commit"
    try:
        raw = read_without_atime(metadata / "index")
    except MetadataUnreadable as exc:
        return True, f"the git index could not be read ({exc.reason})"
    try:
        entries, root_valid = _index_entries(raw)
    except (ValueError, IndexError, struct.error) as exc:
        return True, f"the git index is not a shape this reader parses ({exc})"
    if not entries:
        return True, "the git index tracks no path, so no tree could be compared with it"
    if not root_valid:
        return True, (
            "the git index carries no intact cache-tree root, which is how a staged-but-uncommitted "
            "change reads: the worktree may equal the index while the index differs from the commit"
        )
    for entry in entries:
        name = entry["name"]
        if entry["stage"] != 0:
            return True, f"{name!r} is a conflicted index entry"
        if entry["extended_flags"]:
            return True, f"{name!r} carries index flags this reader does not interpret"
        if entry["mode"] not in _GIT_MODES:
            return True, f"{name!r} is recorded with mode {entry['mode']:o}, which this reader does not compare"
        path = root / str(name)
        try:
            item = path.lstat()
        except OSError:
            return True, f"the tracked path {name!r} is absent from the worktree"
        if entry["mode"] == _GIT_MODE_SYMLINK:
            if not stat.S_ISLNK(item.st_mode):
                return True, f"the tracked symlink {name!r} is not a symlink in the worktree"
        elif not stat.S_ISREG(item.st_mode) or stat.S_ISLNK(item.st_mode):
            return True, f"the tracked file {name!r} is not a regular file in the worktree"
        elif bool(item.st_mode & 0o100) != (entry["mode"] == _GIT_MODE_EXECUTABLE):
            return True, f"the tracked file {name!r} differs from the index in its executable bit"
        try:
            observed = _blob_sha1(path, int(entry["mode"]))
        except OSError as exc:
            return True, f"the tracked path {name!r} could not be hashed ({exc.__class__.__name__})"
        if observed != entry["sha1"]:
            return True, f"the tracked path {name!r} differs in content from the index"
    return False, (
        f"every one of the {len(entries)} paths the git index tracks matches the worktree and the "
        "index's cache-tree root is intact (untracked content is not inspected)"
    )
