#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only THREE-WAY classifier for ADR-0022 decision 4: greenfield, brownfield, or ask.

ADR-0022 decision 4 says greenfield means no relevant operating-contract surface is occupied
and brownfield means at least one is. Read as a two-way rule it is unimplementable, because
no primary source names a single predicate path: `issues/09` line 22, ADR-0022 lines 38-39,
and `to-spec-handoff.md` lines 241-243 each write "guidance, queue, decision, toolchain, hook
or CI surface" and stop. Guessing the list is the harm, not the gap. Adopting
`.github/workflows/` as THE CI predicate classifies every GitLab, Jenkins, Buildkite, and
Woodpecker repository as greenfield and hands it a full proposed baseline, which ADR-0022
lines 20-21 reject by name.

So this module answers with three verdicts and the third one is a question:

* `brownfield` -- a named surface is OCCUPIED. A positive observation, so an incomplete
  predicate list cannot make this verdict wrong; it can only make it un-reached.
* `greenfield` -- the repository is PROVABLY empty on every axis this module can observe:
  no occupied surface, no top-level content outside a small allowlist, and either exactly
  one parentless commit on the only ref that exists with that commit's tree free of every
  named surface and of any unallowlisted top-level entry, or no commit at all in a
  repository whose object store and reflog are also empty. Narrow and hard to earn,
  because greenfield is the verdict that authorizes writing a baseline into someone's
  repository.
* `refuse-and-ask` -- anything else, with the ambiguity NAMED. A bare "cannot determine" is
  useless to the human who has to answer.

That asymmetry is the whole design. A missing predicate costs a REFUSAL rather than a wrong
baseline: a repository with no `.github` but obvious existing content fails the emptiness
proof and lands in refuse-and-ask, never in greenfield. The candidate table below is
therefore deliberately NON-EXHAUSTIVE and safe to extend; adding an entry moves repositories
from refuse-and-ask toward brownfield, which is the cheap direction.

TWO TREES, NOT ONE. A surface is occupied when it is in the WORKING tree or in the COMMITTED
tree, and reading only the first was a defect of exactly the shape the three-way design exists
to prevent: a repository whose HEAD commit carries `AGENTS.md`, `.gitlab-ci.yml`, and
`.github/workflows/ci.yml` -- committed, then removed from the checkout -- was reported
greenfield with zero ambiguities, which is the GitLab misclassification and the full-baseline
harm ADR-0022 lines 20-21 reject by name. So greenfield now also requires the committed tree
to be free of every candidate and of any top-level entry outside the allowlist, and an
allowlisted NAME is only allowlisted when it is a regular file: a directory or symlink called
`LICENSE` can hide a whole occupied tree beneath a permitted name.

THREE OUTCOMES AT EVERY LINK, AND THE THIRD NEVER COLLAPSES INTO THE FIRST. The chain from HEAD
to a tree is HEAD parse -> branch name -> loose ref -> packed ref -> object id -> object type ->
commit headers -> tree -> entry mode, and each link can end in one of exactly three states:
(a) RESOLVED, and here is what it points at; (b) PROVABLY ABSENT, a genuinely unborn branch in a
genuinely empty repository; (c) PRESENT BUT UNREADABLE OR MALFORMED, which is refuse-and-ask.
Every defect this module has had is (c) answered as (b) at some link -- the same false-empty
conclusion at a different depth. It was first the commit tree (read the checkout, never HEAD's
tree), then the ref one step earlier: a `packed-refs` value that failed `_is_object_id` --
truncated, prefixed, uppercased, or duplicated -- fell out of the lookup as None and was read as
an unborn branch, so a repository with a full history and a committed `.gitlab-ci.yml` came back
greenfield with ZERO ambiguities. `resolve_sole_ref` therefore returns a STATE, not an
`oid or None`, and `REF_UNBORN` is a claim it has to earn.

Absence only ever proves emptiness when there is nothing left that could contradict it, so the
proof is anchored at both ends. An unborn branch is believed only in a repository whose object
store AND reflog are empty -- the shape `git init` leaves -- because a deleted branch, an emptied
`packed-refs`, and a never-written one are identical on disk while the commits sit in `objects`.
And `None` from `_read_small` now means ABSENT and nothing else: a `packed-refs` that is a FIFO or
a directory used to empty the entire packed ref surface silently, and a `refs` path that is a
plain FILE used to empty the loose one, each turning a real branch into an unborn one. The
distinction between the two is deliberate per path: a plain file at `docs` IS conclusive proof
that `docs/adr` cannot exist, while a plain file at `.git/refs` is a malformation that proves
nothing about what refs this repository has.

THE COMMITTED WALK IS PREFIX-DIRECTED AND BOUNDED. It reads the root tree plus only those
subtrees whose path is a proper prefix of some candidate (`docs`, `.github`, `.config/mise`,
and so on), so it needs at most `len(CANDIDATE_PREFIXES) + 1` tree objects at a depth of at
most the deepest candidate. `MAX_TREE_OBJECTS` and `MAX_TREE_DEPTH` are headroom over those
derived figures, not a policy, and EXCEEDING EITHER IS A REFUSAL: the bound emits a
`commit-tree` ambiguity naming the path it stopped at rather than concluding absence. Not
descending further is safe rather than lossy, because any unallowlisted top-level entry ALREADY
blocks greenfield -- a deeper walk could only upgrade that refusal to a positive brownfield
naming, never rescue a greenfield. Every other way the walk can fail to complete is a named
`commit-tree` ambiguity too: a packed tree, an unparsable tree, an object that is not the tree
its parent claimed, a submodule gitlink whose content lives in another repository, a non-UTF-8
entry name. A tree whose id is the well-known empty-tree hash is proven empty WITHOUT a read,
because that id is the hash of the empty tree's bytes.

WHAT GREENFIELD DOES NOT PROVE. Two occupied surfaces leave no filesystem trace at all. An
external tracker -- GitHub Issues, Jira, Linear -- occupies the queue surface invisibly, and
a forge-side required check occupies the CI surface invisibly. Nothing here can see either.
The commit-emptiness requirement is what BOUNDS that risk, not what disproves it: a
repository with at most one parentless commit and no other ref is very unlikely to carry a
live external contract. Do not read a greenfield verdict as evidence about anything outside
this checkout, and do not read it as evidence about content this module did not walk (packed
history is refused rather than inspected).

Custody is fd-based, matching `repository-contract.py`. Every intermediate path component is
opened with `O_NOFOLLOW | O_DIRECTORY` and the final component is `lstat`-ed through that
descriptor, so a symlinked PARENT cannot redirect a check outside the repository and no
second path lookup exists to swap underneath a check. A symlinked component makes the
occupancy of that candidate UNDETERMINED -- named as an ambiguity, never silently reported
absent, because "absent" is what would let a redirected check earn greenfield. Candidate
final components are never opened, only `lstat`-ed, so a FIFO at a candidate path cannot
block this process.

Offline and read-only. No subprocess, no network, no write to the target. That rules Git out
as a helper, so the commit-emptiness proof reads `.git` directly: HEAD, the loose and packed
ref surfaces, at most one loose commit object, and the bounded set of loose tree objects that
commit reaches -- each through bounded zlib. Anything it cannot read -- packed objects, a
reftable backend, a detached HEAD, a symref chain -- is an ambiguity, never an assumption.

Exit codes follow Implementation Decision 9. 0 is a completed classification INCLUDING
`refuse-and-ask`: the query succeeded and the verdict is the answer, so a caller that treats
a nonzero code as "the tool failed" is not misled about a question it must relay. 2 is this
tool's own grammar and invalid input, which is a non-absolute `--target`. 3 is a clean
refusal to inspect at all before any effect: a missing or unopenable target, or a target that
is not a Git repository -- `.git` absent, a symlink, or a `gitdir:` redirect file. 1 is an
unexpected internal failure. 4 is UNREACHABLE by construction and that is a property of the
tool, not an omission: 4 reports an admitted partial or unknown EFFECT, and this module's
only output is bytes on stdout, so there is no effect to admit and no moment at which one
becomes true. `/sdlc-init` step 2 creates the repository (`git init`) before classification,
which is why an absent `.git` is a refusal to inspect rather than the emptiest greenfield.

Implementation Decision 10: this is evidence, not authority. The result names what was seen
and nothing else -- no readiness, ownership, trust, route, or tool identity, and no statement
that activation may proceed. A greenfield verdict does not authorize a baseline write; the
plan, the digest approval, and the human grant do that, and each is somebody else's job.
"""
from __future__ import annotations

import argparse
import contextlib
import errno
import json
import os
import stat
import sys
import zlib
from pathlib import Path
from typing import Any, Iterator

RESULT_SCHEMA = "agentic-sdlc/repository-class-result@1"
GIT_DIRECTORY_NAME = ".git"

# Implementation Decision 9: 2 is grammar or invalid input, 3 is a clean refusal before any
# effect. 0 covers every completed classification, refuse-and-ask included.
INVALID_INPUT_CODE = 2
INSPECT_REFUSAL_CODE = 3

VERDICT_BROWNFIELD = "brownfield"
VERDICT_GREENFIELD = "greenfield"
VERDICT_ASK = "refuse-and-ask"
VERDICTS = (VERDICT_BROWNFIELD, VERDICT_GREENFIELD, VERDICT_ASK)

RESULT_KEYS = frozenset(
    {"schema", "command", "status", "exit_code", "target", "verdict", "occupied", "ambiguities", "reasons"}
)

# Screened against RESULT_KEYS by the test suite so no result FIELD claims authority this
# module cannot hold. Values are prose about what was observed and are not screened -- the
# same trade `repository-contract.py` makes, for the same reason.
PROHIBITED_CLAIM_TOKENS = ("readiness", "ready", "ownership", "owned", "trust", "route", "authoriz")

# The closed ambiguity vocabulary. Each record carries the kind plus the exact thing seen.
KIND_CONTENT = "unclassified-content"
KIND_UNDETERMINED = "undetermined-surface"
KIND_HISTORY = "commit-history"
KIND_REFS = "ref-surface"
KIND_HEAD = "head-form"
KIND_TREE = "commit-tree"

# Operating-contract surfaces. The six named by the primary sources, plus `contract` for the
# one predicate a primary source DOES name: ADR-0022 decision 2's `.agentic-sdlc/repo.toml`.
# Every path is repository-root relative and POSIX-separated. Non-exhaustive by design.
CANDIDATES: tuple[tuple[str, str], ...] = (
    # Canonical host-neutral guidance and per-host agent configuration (issue 09).
    ("guidance", "AGENTS.md"),
    ("guidance", "CLAUDE.md"),
    ("guidance", "GEMINI.md"),
    ("guidance", "CONVENTIONS.md"),
    ("guidance", ".cursorrules"),
    ("guidance", ".clinerules"),
    ("guidance", ".windsurfrules"),
    ("guidance", ".goosehints"),
    ("guidance", ".aider.conf.yml"),
    ("guidance", ".cursor"),
    ("guidance", ".claude"),
    ("guidance", ".codex"),
    ("guidance", ".gemini"),
    ("guidance", ".github/copilot-instructions.md"),
    # The authoritative queue. A tracker that lives in a hosted service is invisible here;
    # see the greenfield limits in the module docstring.
    ("queue", ".seeds"),
    ("queue", ".beads"),
    ("queue", ".backlog"),
    ("queue", ".taskmaster"),
    # Decision records and the domain glossary (ADR-0022 decision 2, issue 09).
    ("decision", "docs/adr"),
    ("decision", "docs/adrs"),
    ("decision", "docs/decisions"),
    ("decision", "docs/architecture/decisions"),
    ("decision", "doc/adr"),
    ("decision", "adr"),
    ("decision", ".adr-dir"),
    ("decision", "CONTEXT.md"),
    # Pinned toolchain, build, and task-runner contracts.
    ("toolchain", "mise.toml"),
    ("toolchain", ".mise.toml"),
    ("toolchain", ".mise/config.toml"),
    ("toolchain", ".config/mise/config.toml"),
    ("toolchain", ".tool-versions"),
    ("toolchain", ".nvmrc"),
    ("toolchain", ".python-version"),
    ("toolchain", ".ruby-version"),
    ("toolchain", "package.json"),
    ("toolchain", "pyproject.toml"),
    ("toolchain", "setup.py"),
    ("toolchain", "setup.cfg"),
    ("toolchain", "requirements.txt"),
    ("toolchain", "Cargo.toml"),
    ("toolchain", "go.mod"),
    ("toolchain", "Gemfile"),
    ("toolchain", "pom.xml"),
    ("toolchain", "build.gradle"),
    ("toolchain", "build.gradle.kts"),
    ("toolchain", "build.sbt"),
    ("toolchain", "composer.json"),
    ("toolchain", "mix.exs"),
    ("toolchain", "deno.json"),
    ("toolchain", "deno.jsonc"),
    ("toolchain", "Makefile"),
    ("toolchain", "GNUmakefile"),
    ("toolchain", "justfile"),
    ("toolchain", "Justfile"),
    ("toolchain", "Taskfile.yml"),
    ("toolchain", "Taskfile.yaml"),
    ("toolchain", "CMakeLists.txt"),
    ("toolchain", "flake.nix"),
    ("toolchain", "shell.nix"),
    ("toolchain", "default.nix"),
    ("toolchain", "Dockerfile"),
    ("toolchain", "docker-compose.yml"),
    ("toolchain", "compose.yaml"),
    # Git hook managers. `.git/hooks` itself is scanned separately.
    ("hook", "lefthook.yml"),
    ("hook", "lefthook.yaml"),
    ("hook", ".lefthook.yml"),
    ("hook", ".lefthook.yaml"),
    ("hook", ".pre-commit-config.yaml"),
    ("hook", ".husky"),
    ("hook", ".githooks"),
    # CI. Enumerating more than one forge is the point of this table.
    ("ci", ".github/workflows"),
    ("ci", ".gitlab-ci.yml"),
    ("ci", ".gitlab-ci.yaml"),
    ("ci", "Jenkinsfile"),
    ("ci", ".circleci"),
    ("ci", ".buildkite"),
    ("ci", ".woodpecker"),
    ("ci", ".woodpecker.yml"),
    ("ci", ".woodpecker.yaml"),
    ("ci", ".drone.yml"),
    ("ci", ".travis.yml"),
    ("ci", ".cirrus.yml"),
    ("ci", ".semaphore"),
    ("ci", ".teamcity"),
    ("ci", ".harness"),
    ("ci", "azure-pipelines.yml"),
    ("ci", "bitbucket-pipelines.yml"),
    ("ci", "appveyor.yml"),
    ("ci", ".appveyor.yml"),
    ("ci", ".forgejo/workflows"),
    ("ci", ".gitea/workflows"),
    # This bundle's own tracked activation contract (ADR-0022 decision 2).
    ("contract", ".agentic-sdlc"),
)

# Top-level entries a provably-empty repository may contain. Everything else at the root is
# an `unclassified-content` ambiguity, which is what stops "obvious existing content" from
# earning greenfield when no enumerated surface happens to match it.
CONTENT_ALLOWLIST = frozenset(
    {
        GIT_DIRECTORY_NAME,
        "README",
        "README.md",
        "README.rst",
        "README.txt",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "LICENCE",
        "COPYING",
        "NOTICE",
        ".gitignore",
        ".gitattributes",
    }
)

MAX_NAMED_ENTRIES = 20  # Bounds every evidence list so output stays diffable.
MAX_REF_WALK_ENTRIES = 4096
MAX_REF_WALK_DEPTH = 16
MAX_SMALL_FILE_BYTES = 1 << 20
MAX_OBJECT_BYTES = 1 << 16
HEAD_BRANCH_PREFIX = "ref: refs/heads/"

# Bounds for the committed-tree walk. An unbounded recursive tree read is a RAM hazard and a
# recursion hazard, so the walk is iterative and stops at both of these. The prefix-directed
# walk needs `len(CANDIDATE_PREFIXES) + 1` objects at the deepest candidate's depth; the test
# suite asserts both derived figures stay under these ceilings, so a candidate table that
# outgrows them fails the gate instead of silently turning repositories into refusals.
MAX_TREE_OBJECTS = 16
MAX_TREE_DEPTH = 8

# The three outcomes every link from HEAD to a tree must be able to report. `REF_UNBORN` is a
# PROOF that no commit exists; `REF_UNDETERMINED` is the admission that this module could not
# tell. Collapsing the second into the first is what reported a full repository as greenfield.
REF_RESOLVED = "resolved"
REF_UNBORN = "unborn"
REF_UNDETERMINED = "undetermined"

# `git init` leaves `objects/info` and `objects/pack` EMPTY, so 258 top-level names is the real
# ceiling; this is headroom over it and exceeding it is a refusal, not an assumption of emptiness.
MAX_OBJECT_STORE_ENTRIES = 512

# Git's own well-known empty-tree ids, SHA-1 and SHA-256. Matching one is PROOF the tree is
# empty without reading anything, because the id is the hash of the empty tree's bytes -- and
# `git commit-tree` against an empty index yields this id without writing a loose object.
EMPTY_TREE_OIDS = frozenset(
    {
        "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
        "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
    }
)

# Tree entry modes, as Git writes them.
GIT_MODE_TREE = 0o40000
GIT_MODE_GITLINK = 0o160000
GIT_MODE_SYMLINK = 0o120000
GIT_MODE_BLOBS = (0o100644, 0o100755)
# Every mode Git writes. An entry outside this set cannot be interpreted, so it is NAMED: a
# directory-flavoured mode this walk does not recognize would otherwise be skipped silently and
# every candidate beneath it reported absent.
GIT_MODES = frozenset({GIT_MODE_TREE, GIT_MODE_GITLINK, GIT_MODE_SYMLINK, *GIT_MODE_BLOBS})


def _candidate_prefixes() -> frozenset[str]:
    """Every proper directory prefix of a candidate path, which is exactly what to descend into."""
    prefixes: set[str] = set()
    for _, relative in CANDIDATES:
        parts = relative.split("/")
        for index in range(1, len(parts)):
            prefixes.add("/".join(parts[:index]))
    return frozenset(prefixes)


CANDIDATE_PATHS = frozenset(relative for _, relative in CANDIDATES)
CANDIDATE_PREFIXES = _candidate_prefixes()


class InspectionRefusal(Exception):
    """A refusal to inspect at all, before any effect. Carries its reason and exit code."""

    def __init__(self, reason: str, code: int = INSPECT_REFUSAL_CODE) -> None:
        super().__init__(reason)
        self.reason, self.code = reason, code


class UndeterminedPath(Exception):
    """One path could not be resolved conclusively, so its occupancy is UNKNOWN.

    Distinct from `FileNotFoundError` on purpose. "Absent" is a conclusion that feeds the
    greenfield proof; "undetermined" must never be able to.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class MalformedObject(Exception):
    """One Git file or object did not parse. Carries the exact malformation, not just an errno.

    A bare `EINVAL` would tell the human "unparsable" and nothing else -- and `_detail` reduces
    every `OSError` to its errno name, so a message passed to `OSError` never reaches the
    output at all. This module's whole contract is that a refusal NAMES what made it ambiguous,
    so anything with a malformation to describe raises THIS instead.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


# Every way an observation can fail to complete. Each becomes a NAMED ambiguity, never a
# silent absence. `FileNotFoundError` is deliberately NOT here: absence is a conclusion.
READ_FAILURES: tuple[type[BaseException], ...] = (UndeterminedPath, MalformedObject, OSError, UnicodeError, zlib.error)


class Observation:
    """The accumulating evidence. Nothing here is a decision; `verdict` derives from it."""

    def __init__(self) -> None:
        self.occupied: list[dict[str, str]] = []
        self.ambiguities: list[dict[str, str]] = []

    def occupy(self, surface: str, path: str, kind: str) -> None:
        self.occupied.append({"kind": kind, "path": path, "surface": surface})

    def ambiguous(self, kind: str, detail: str) -> None:
        self.ambiguities.append({"detail": detail, "kind": kind})

    def verdict(self) -> str:
        if self.occupied:
            return VERDICT_BROWNFIELD
        if self.ambiguities:
            return VERDICT_ASK
        return VERDICT_GREENFIELD

    def sorted_occupied(self) -> list[dict[str, str]]:
        unique = {(item["surface"], item["path"]): item for item in self.occupied}
        return [unique[key] for key in sorted(unique)]

    def sorted_ambiguities(self) -> list[dict[str, str]]:
        unique = {(item["kind"], item["detail"]): item for item in self.ambiguities}
        return [unique[key] for key in sorted(unique)]


def canonical_bytes(value: Any) -> bytes:
    """Canonical JSON plus a trailing newline, matching the activation family."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def _errno_name(exc: OSError) -> str:
    """A stable errno name. `os.strerror` is locale-dependent and would break byte-stability."""
    return errno.errorcode.get(exc.errno, f"errno {exc.errno}")


def _detail(exc: BaseException) -> str:
    """One stable, locale-independent phrase for any read failure."""
    if isinstance(exc, (UndeterminedPath, MalformedObject)):
        return exc.detail
    if isinstance(exc, OSError):
        return _errno_name(exc)
    if isinstance(exc, UnicodeError):
        return "not UTF-8"
    if isinstance(exc, zlib.error):
        return "malformed zlib stream"
    return type(exc).__name__


def _node_kind(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def _open_at(name: str, dir_fd: int, *, directory: bool) -> int:
    """Open one path component, refusing symlinks and never blocking on a FIFO."""
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    return os.open(name, flags, dir_fd=dir_fd)


def _classify_failed_component(parent_fd: int, component: str, exc: OSError) -> Exception:
    """Decide whether a failed component open is a conclusive ABSENCE or UNDETERMINED.

    This exists because `O_NOFOLLOW | O_DIRECTORY` on a symlink-to-directory returns ENOTDIR
    on Linux, not ELOOP, which `NotADirectoryError` makes indistinguishable from an ordinary
    file sitting where a directory was expected. Trusting the errno therefore reported a
    symlinked PARENT as "this candidate cannot exist" -- the precise redirect-earns-greenfield
    defect the fd-based custody is here to prevent. So the component is stat-ed, without
    following, to establish what actually sits there.
    """
    try:
        info = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return FileNotFoundError(errno.ENOENT, "component disappeared")
    except OSError:
        return UndeterminedPath(f"{component}: {_errno_name(exc)}")
    if stat.S_ISLNK(info.st_mode):
        return UndeterminedPath(f"{component} is a symlink")
    if not stat.S_ISDIR(info.st_mode):
        # A real non-directory in the middle of the path: nothing can exist beneath it.
        return FileNotFoundError(errno.ENOTDIR, f"{component} is a {_node_kind(info.st_mode)}")
    return UndeterminedPath(f"{component}: {_errno_name(exc)}")


@contextlib.contextmanager
def _descend(dir_fd: int, components: tuple[str, ...]) -> Iterator[int]:
    """Yield a descriptor for the directory reached by opening each component in turn.

    Custody, not convenience: each component is opened with `O_NOFOLLOW`, so a symlinked
    intermediate directory cannot silently redirect the caller's check to another tree. A
    component that fails to open is classified rather than assumed absent.
    """
    opened: list[int] = []
    try:
        current = dir_fd
        for component in components:
            try:
                current = _open_at(component, current, directory=True)
            except FileNotFoundError:
                raise
            except OSError as exc:
                raise _classify_failed_component(current, component, exc) from exc
            opened.append(current)
        yield current
    finally:
        for fd in reversed(opened):
            os.close(fd)


def _malformed_directory(exc: FileNotFoundError, relative: str) -> str | None:
    """None when a structural `.git` directory is genuinely ABSENT, else what to name instead.

    `_classify_failed_component` reports a real non-directory component as an ENOTDIR-flavoured
    `FileNotFoundError`, because for a CANDIDATE path nothing can exist beneath a plain file and
    that is a conclusive absence. For a directory GIT ITSELF owns -- `refs`, `hooks`, `objects` --
    the same shape means the surface is MALFORMED, and "no loose refs" read off a `refs` FILE is
    exactly the false-empty conclusion this module exists to refuse. ENOENT keeps its meaning: a
    fully packed repository legitimately has no `refs` tree at all.

    A detail is RETURNED rather than raised so each caller stays in charge of how it reports:
    raising here would escape a sibling `except READ_FAILURES` clause and surface as an internal
    failure instead of the named ambiguity it is.
    """
    if exc.errno == errno.ENOENT:
        return None
    return f"{GIT_DIRECTORY_NAME}/{relative} is not a directory"


def _lstat_at(dir_fd: int, relative: str) -> os.stat_result | None:
    """`lstat` a repository-relative path through verified descriptors, or None if absent.

    The final component is never OPENED, only stat-ed without following, so a symlink is
    reported as itself and a FIFO cannot block this process.
    """
    components = tuple(relative.split("/"))
    with _descend(dir_fd, components[:-1]) as parent_fd:
        try:
            return os.stat(components[-1], dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None


def scan_candidates(target_fd: int, observed: Observation) -> None:
    """Record every occupied candidate surface, and name every one it could not determine."""
    for surface, relative in CANDIDATES:
        try:
            info = _lstat_at(target_fd, relative)
        except FileNotFoundError:
            # A missing or genuinely non-directory intermediate component means the candidate
            # cannot exist. That is a conclusive absence, not an ambiguity.
            continue
        except READ_FAILURES as exc:
            # A symlinked or unreadable parent leaves occupancy UNKNOWN, and recording it as
            # absent is what would let a redirected subtree earn greenfield.
            observed.ambiguous(KIND_UNDETERMINED, f"{relative}: {_detail(exc)}")
            continue
        if info is not None:
            observed.occupy(surface, relative, _node_kind(info.st_mode))


def scan_git_hooks(git_fd: int, observed: Observation) -> None:
    """Report installed `.git/hooks` entries, ignoring the `.sample` files `git init` writes."""
    try:
        with _descend(git_fd, ("hooks",)) as hooks_fd:
            names = sorted(name for name in os.listdir(hooks_fd) if not name.endswith(".sample"))
    except FileNotFoundError as exc:
        # Absent is a conclusion; a `hooks` path that exists but is not a directory leaves the
        # hook surface UNKNOWN, and reporting no hooks off a malformed one would be an absence
        # this module never observed.
        malformed = _malformed_directory(exc, "hooks")
        if malformed is not None:
            observed.ambiguous(KIND_UNDETERMINED, malformed)
        return
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_UNDETERMINED, f"{GIT_DIRECTORY_NAME}/hooks: {_detail(exc)}")
        return
    for name in names[:MAX_NAMED_ENTRIES]:
        observed.occupy("hook", f"{GIT_DIRECTORY_NAME}/hooks/{name}", "file")


def _is_allowlisted_working_entry(target_fd: int, name: str) -> bool:
    """Whether one top-level entry is permitted in a provably-empty repository.

    An allowlisted NAME is not enough: a directory or symlink called `LICENSE` can hide an
    entire occupied tree beneath a permitted name, and `_lstat_at` never descends into it. So
    the allowlist admits regular files only, plus the already-verified `.git` directory. A name
    that cannot be stat-ed is reported rather than waved through, because "absent" and
    "unreadable" must not share an answer here.
    """
    if name == GIT_DIRECTORY_NAME:
        return True  # `open_git_directory` already proved this is a real directory.
    if name not in CONTENT_ALLOWLIST:
        return False
    try:
        info = os.stat(name, dir_fd=target_fd, follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode)


def scan_content(target_fd: int, observed: Observation) -> None:
    """Name top-level entries outside the allowlist. Existing content is not greenfield."""
    try:
        names = sorted(name for name in os.listdir(target_fd) if not _is_allowlisted_working_entry(target_fd, name))
    except OSError as exc:
        observed.ambiguous(KIND_UNDETERMINED, f".: {_errno_name(exc)}")
        return
    if not names:
        return
    shown = ", ".join(names[:MAX_NAMED_ENTRIES])
    suffix = "" if len(names) <= MAX_NAMED_ENTRIES else f" (+{len(names) - MAX_NAMED_ENTRIES} more)"
    observed.ambiguous(KIND_CONTENT, f"{len(names)} entries: {shown}{suffix}")


def _read_small(dir_fd: int, relative: str, *, limit: int = MAX_SMALL_FILE_BYTES) -> bytes | None:
    """Read a small regular file inside `.git`. None means ABSENT and nothing else.

    Each intermediate component is descended separately. Passing a multi-component path to
    one `openat` would protect only the final component, so `refs/heads/main` would be read
    through a symlinked `refs`.

    A path that EXISTS but is not a regular file raises rather than returning None, because
    every caller here reads None as "this file is not there" and turns that into a conclusion:
    a `packed-refs` FIFO or directory silently emptied the whole packed ref surface, and a
    packed branch then looked exactly like an unborn one. Present-but-unreadable is a third
    outcome and it has to stay distinguishable from absence.
    """
    components = tuple(relative.split("/"))
    try:
        with _descend(dir_fd, components[:-1]) as parent_fd:
            fd = _open_at(components[-1], parent_fd, directory=False)
    except FileNotFoundError:
        return None
    try:
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode):
            raise UndeterminedPath(f"{relative} is not a regular file ({_node_kind(mode)})")
        data = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise OSError(errno.EFBIG, "file too large")
    return data


def read_head_branch(git_fd: int, observed: Observation) -> str | None:
    """Return the branch HEAD points at, or None when HEAD is not a usable branch symref.

    A detached HEAD, a symref outside `refs/heads/`, or an unparsable HEAD is an ambiguity:
    the commit-emptiness proof needs one named branch, and guessing which commit "the" HEAD
    means is exactly the assumption this module refuses to make.
    """
    try:
        raw = _read_small(git_fd, "HEAD", limit=4096)
    except READ_FAILURES as exc:
        raise InspectionRefusal(f"cannot read {GIT_DIRECTORY_NAME}/HEAD: {_detail(exc)}") from exc
    if raw is None:
        raise InspectionRefusal(f"target is not a Git repository: {GIT_DIRECTORY_NAME}/HEAD is absent")
    try:
        text = raw.decode("utf-8", "strict").strip()
    except UnicodeError:
        observed.ambiguous(KIND_HEAD, f"{GIT_DIRECTORY_NAME}/HEAD is not UTF-8")
        return None
    if len(text.splitlines()) > 1:
        # A multi-line HEAD is not a shape Git writes, and taking the first line would pick one
        # branch out of a file that names more than one.
        observed.ambiguous(KIND_HEAD, f"{GIT_DIRECTORY_NAME}/HEAD is not a single line")
        return None
    if not text.startswith(HEAD_BRANCH_PREFIX):
        observed.ambiguous(KIND_HEAD, f"{GIT_DIRECTORY_NAME}/HEAD is not a branch symref")
        return None
    branch = text[len(HEAD_BRANCH_PREFIX) :]
    unusable = (
        not branch
        or branch.startswith("/")
        or any(part in ("", ".", "..") for part in branch.split("/"))
        # Git's own `check-ref-format` forbids whitespace and control characters. One here means
        # the name this module would look up is not the name Git would resolve.
        or any(character.isspace() or ord(character) < 0x20 for character in branch)
    )
    if unusable:
        observed.ambiguous(KIND_HEAD, f"{GIT_DIRECTORY_NAME}/HEAD names an unusable branch")
        return None
    return f"refs/heads/{branch}"


def _walk_loose_refs(refs_fd: int, prefix: str, depth: int) -> Iterator[str]:
    if depth > MAX_REF_WALK_DEPTH:
        raise MalformedObject(f"{GIT_DIRECTORY_NAME}/{prefix} nests deeper than {MAX_REF_WALK_DEPTH} levels")
    for name in sorted(os.listdir(refs_fd)):
        relative = f"{prefix}/{name}"
        info = os.stat(name, dir_fd=refs_fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            with _descend(refs_fd, (name,)) as child_fd:
                yield from _walk_loose_refs(child_fd, relative, depth + 1)
        else:
            yield relative


def _loose_ref_names(git_fd: int) -> list[str]:
    """Every loose ref name under `.git/refs`. An ABSENT `refs` tree is the only empty answer.

    The narrow `try` is the point. Catching `FileNotFoundError` around the WALK as well turned
    any mid-walk disappearance -- and, through `_classify_failed_component`, a `refs` path that
    is a plain FILE -- into "this repository has no loose refs", after which a packed or deleted
    branch was indistinguishable from an unborn one.
    """
    try:
        refs_fd = _open_at("refs", git_fd, directory=True)
    except FileNotFoundError:
        return []
    except OSError as exc:
        classified = _classify_failed_component(git_fd, "refs", exc)
        if isinstance(classified, FileNotFoundError):
            malformed = _malformed_directory(classified, "refs")
            raise UndeterminedPath(malformed or f"{GIT_DIRECTORY_NAME}/refs disappeared while it was read") from exc
        raise classified from exc
    try:
        names: list[str] = []
        for relative in _walk_loose_refs(refs_fd, "refs", 0):
            names.append(relative)
            if len(names) > MAX_REF_WALK_ENTRIES:
                raise MalformedObject(f"{GIT_DIRECTORY_NAME}/refs holds more than {MAX_REF_WALK_ENTRIES} refs")
        return names
    finally:
        os.close(refs_fd)


def _packed_ref_pairs(git_fd: int) -> list[tuple[str, str]]:
    """Parse `.git/packed-refs` into (object id, ref name) pairs, or [] when the file is absent.

    The malformation is raised as `MalformedObject` and not `OSError`, because `_detail` reduces
    an `OSError` to its errno name and `EINVAL` alone would not tell the human which line broke.
    """
    raw = _read_small(git_fd, "packed-refs")
    if raw is None:
        return []
    pairs: list[tuple[str, str]] = []
    for number, line in enumerate(raw.decode("utf-8", "strict").splitlines(), start=1):
        if not line or line.startswith("#") or line.startswith("^"):
            continue
        parts = line.split(" ", 1)
        if len(parts) != 2 or not parts[1].strip():
            raise MalformedObject(f"{GIT_DIRECTORY_NAME}/packed-refs line {number} is not '<object id> <ref name>'")
        pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs


def resolve_sole_ref(git_fd: int, branch: str, observed: Observation) -> tuple[str, str | None]:
    """Resolve `branch` to one of THREE outcomes, while naming every other ref that exists.

    Returns `(REF_RESOLVED, oid)`, `(REF_UNBORN, None)`, or `(REF_UNDETERMINED, None)`. The third
    one is why this returns a state at all. It used to return a bare `oid or None`, so a
    `packed-refs` value that failed `_is_object_id` -- truncated, prefixed, uppercased, or
    duplicated -- fell out of the lookup loop as None and was read one frame up as an UNBORN
    BRANCH. A real repository with a full history and a committed `.gitlab-ci.yml` was reported
    greenfield with zero ambiguities: the same false-empty conclusion as reading no commit tree
    at all, one link earlier in the chain.

    A tag, another branch, a remote ref, or a ref backend this module cannot read is NAMED, since
    each one means commits exist that the single-commit proof would never look at. Those name an
    ambiguity and let the resolution continue, because an occupied surface found in the resolved
    commit's tree is a positive observation worth reporting and greenfield is already unreachable
    once anything is named.
    """
    # Which storage this module could NOT read, if any. A name rather than a flag, because the
    # unborn branch it blocks has to be able to say why it was blocked: a boolean here was an
    # equivalent mutant -- removing it changed no output, since the backend ambiguity below
    # already forced refuse-and-ask -- and an unfalsifiable guard is one nothing protects.
    unread_backend: str | None = None
    try:
        reftable = _lstat_at(git_fd, "reftable")
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_REFS, f"ref surface is not readable: {_detail(exc)}")
        return REF_UNDETERMINED, None
    if reftable is not None:
        observed.ambiguous(KIND_REFS, f"{GIT_DIRECTORY_NAME}/reftable backend is not read offline")
        unread_backend = f"{GIT_DIRECTORY_NAME}/reftable"
    try:
        loose = _loose_ref_names(git_fd)
        packed = _packed_ref_pairs(git_fd)
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_REFS, f"ref surface is not readable: {_detail(exc)}")
        return REF_UNDETERMINED, None
    foreign = sorted({name for name in loose if name != branch} | {name for _, name in packed if name != branch})
    if foreign:
        shown = ", ".join(foreign[:MAX_NAMED_ENTRIES])
        suffix = "" if len(foreign) <= MAX_NAMED_ENTRIES else f" (+{len(foreign) - MAX_NAMED_ENTRIES} more)"
        observed.ambiguous(KIND_REFS, f"{len(foreign)} refs beyond {branch}: {shown}{suffix}")
    packed_oids = sorted({packed_oid for packed_oid, name in packed if name == branch})
    if branch in loose:
        try:
            raw = _read_small(git_fd, branch, limit=4096)
            text = "" if raw is None else raw.decode("utf-8", "strict").strip()
        except READ_FAILURES as exc:
            observed.ambiguous(KIND_REFS, f"{branch} is not readable: {_detail(exc)}")
            return REF_UNDETERMINED, None
        if not _is_object_id(text):
            # A symref chain, an empty file, or a corrupt value. Every one of them means the
            # branch's commit is UNKNOWN, which is not the same as the branch having none.
            observed.ambiguous(KIND_REFS, f"{branch} is not a direct object id")
            return REF_UNDETERMINED, None
        stale = [packed_oid for packed_oid in packed_oids if packed_oid != text]
        if stale:
            # Git resolves the loose value, so this walk follows it too -- but a packed entry at
            # a DIFFERENT id names a second commit in this repository, which no single-commit
            # proof over the loose one can rule out.
            observed.ambiguous(KIND_REFS, f"{branch} is also packed at {', '.join(stale[:MAX_NAMED_ENTRIES])}")
        return REF_RESOLVED, text
    if len(packed_oids) > 1:
        observed.ambiguous(KIND_REFS, f"{branch} is packed at {len(packed_oids)} different object ids")
        return REF_UNDETERMINED, None
    if packed_oids:
        if not _is_object_id(packed_oids[0]):
            observed.ambiguous(KIND_REFS, f"{branch} is packed at a value that is not an object id")
            return REF_UNDETERMINED, None
        return REF_RESOLVED, packed_oids[0]
    if unread_backend is not None:
        # The branch is in neither storage this module read, but the one it could not read may
        # hold it, so its absence HERE proves nothing about whether it is born.
        observed.ambiguous(KIND_REFS, f"{branch} is in neither ref storage, and the unread {unread_backend} could hold it")
        return REF_UNDETERMINED, None
    return REF_UNBORN, None


def _is_object_id(text: str) -> bool:
    return len(text) in (40, 64) and all(character in "0123456789abcdef" for character in text)


def read_loose_object(git_fd: int, oid: str) -> tuple[str, bytes] | None:
    """Return one loose object's declared type and inflated payload, or None if it is packed.

    The type is RETURNED rather than assumed, because "the object my parent said was a tree"
    and "a tree" are different facts, and treating a blob's bytes as tree entries is how a
    walk invents structure that is not there.
    """
    raw = _read_small(git_fd, f"objects/{oid[:2]}/{oid[2:]}")
    if raw is None:
        return None
    engine = zlib.decompressobj()
    inflated = engine.decompress(raw, MAX_OBJECT_BYTES)
    if engine.unconsumed_tail or not engine.eof:
        raise OSError(errno.EFBIG, "object is larger than the inflation bound or is truncated")
    header, separator, payload = inflated.partition(b"\0")
    if not separator:
        raise MalformedObject("object has no type header")
    kind, space, size = header.partition(b" ")
    if not space or not size.isdigit() or int(size) != len(payload):
        raise MalformedObject("object header disagrees with its payload")
    return kind.decode("ascii", "replace"), payload


def parse_tree_entries(payload: bytes, oid_bytes: int) -> list[tuple[int, str, str]]:
    """Parse `<octal mode> <name>\\0<raw oid>` records into (mode, name, oid) triples.

    Strict on purpose. Every malformed shape raises, so `collect_committed_entries` NAMES an
    unparsable tree instead of walking a partial entry list and concluding a surface is absent.
    """
    entries: list[tuple[int, str, str]] = []
    offset, total = 0, len(payload)
    while offset < total:
        space = payload.find(b" ", offset)
        if space <= offset:
            raise MalformedObject("a tree entry has no mode")
        nul = payload.find(b"\0", space + 1)
        if nul <= space + 1:
            raise MalformedObject("a tree entry has no name")
        end = nul + 1 + oid_bytes
        if end > total:
            raise MalformedObject("a tree entry is truncated")
        raw_mode = payload[offset:space]
        if len(raw_mode) > 6 or any(digit not in b"01234567" for digit in raw_mode):
            raise MalformedObject("a tree entry mode is not octal")
        raw_name = payload[space + 1 : nul]
        if b"/" in raw_name or raw_name in (b".", b".."):
            raise MalformedObject("a tree entry name is not one path component")
        # A non-UTF-8 name raises UnicodeError, which is a READ_FAILURE: a name this module
        # cannot render is an ambiguity, never a path it silently skips.
        entries.append((int(raw_mode, 8), raw_name.decode("utf-8", "strict"), payload[nul + 1 : end].hex()))
        offset = end
    return entries


def _git_mode_kind(mode: int) -> str:
    if mode == GIT_MODE_TREE:
        return "directory"
    if mode == GIT_MODE_GITLINK:
        return "submodule"
    if mode == GIT_MODE_SYMLINK:
        return "symlink"
    if mode in GIT_MODE_BLOBS:
        return "file"
    return "other"


def _is_allowlisted_committed_entry(name: str, mode: int) -> bool:
    """Same rule as the working tree: an allowlisted name must be a regular blob.

    `.git` is in the working-tree allowlist because every repository has one; a TREE can never
    legitimately carry that name, so a committed entry claiming it is named, not waved through.
    """
    return name != GIT_DIRECTORY_NAME and name in CONTENT_ALLOWLIST and mode in GIT_MODE_BLOBS


def collect_committed_entries(git_fd: int, tree_oid: str) -> tuple[dict[str, int], list[tuple[str, int]], list[str]]:
    """Walk the committed tree, prefix-directed and bounded, without recursion.

    Returns the modes of every candidate-or-prefix path found, the root tree's entries, and one
    NAMED failure per thing the walk could not resolve. Failures are returned rather than
    concluded: an unreadable subtree means the candidates beneath it are unknown, and unknown
    must never reach the greenfield branch as absence.
    """
    named: dict[str, int] = {}
    root: list[tuple[str, int]] = []
    failures: list[str] = []
    oid_bytes = len(tree_oid) // 2
    pending: list[tuple[str, str, int]] = [("", tree_oid, 0)]
    reads = 0
    while pending:
        prefix, oid, depth = pending.pop(0)
        where = f"HEAD:{prefix}" if prefix else "HEAD root tree"
        if reads >= MAX_TREE_OBJECTS:
            failures.append(f"{where}: the committed tree walk stopped at its {MAX_TREE_OBJECTS}-object bound")
            break
        if depth > MAX_TREE_DEPTH:
            failures.append(f"{where}: the committed tree walk stopped at its {MAX_TREE_DEPTH}-level depth bound")
            continue
        reads += 1
        try:
            parsed = read_loose_object(git_fd, oid)
        except READ_FAILURES as exc:
            failures.append(f"{where}: tree {oid} is not readable: {_detail(exc)}")
            continue
        if parsed is None:
            failures.append(f"{where}: tree {oid} is not a loose object; packed, absent, and alternate objects are not walked offline")
            continue
        kind, payload = parsed
        if kind != "tree":
            failures.append(f"{where}: object {oid} is a {kind}, not the tree its parent named")
            continue
        try:
            entries = parse_tree_entries(payload, oid_bytes)
        except READ_FAILURES as exc:
            failures.append(f"{where}: tree {oid} is unparsable: {_detail(exc)}")
            continue
        for mode, name, child in entries:
            relative = f"{prefix}/{name}" if prefix else name
            if not prefix:
                root.append((name, mode))
            if relative in CANDIDATE_PATHS or relative in CANDIDATE_PREFIXES:
                named[relative] = mode
            if mode not in GIT_MODES:
                # The entry-mode link's third outcome. Only `mode == GIT_MODE_TREE` descends, so
                # an unrecognized mode on a candidate PREFIX would leave every candidate beneath
                # it unexamined while the walk reported nothing at all.
                failures.append(f"HEAD:{relative} has mode {mode:06o}, which is not a mode Git writes, so what it holds is unknown")
            elif mode == GIT_MODE_GITLINK:
                failures.append(f"HEAD:{relative} is a submodule, so its content lives in another repository")
            elif mode == GIT_MODE_TREE and relative in CANDIDATE_PREFIXES:
                pending.append((relative, child, depth + 1))
    return named, root, failures


def prove_committed_tree_is_empty(git_fd: int, tree_oid: str, observed: Observation) -> None:
    """Prove the COMMITTED tree holds no named surface and no unallowlisted top-level entry.

    Reading the working tree alone was the live defect: a repository whose HEAD commit carries
    `.gitlab-ci.yml` has an occupied CI surface even when the checkout no longer shows the file,
    and calling that greenfield hands a full proposed baseline to a repository that is plainly
    not empty (ADR-0022 lines 20-21).
    """
    if tree_oid in EMPTY_TREE_OIDS:
        return  # The id is the hash of the empty tree, so this is proof without a read.
    named, root, failures = collect_committed_entries(git_fd, tree_oid)
    before = len(observed.occupied)
    for surface, relative in CANDIDATES:
        mode = named.get(relative)
        if mode is not None:
            observed.occupy(surface, f"HEAD:{relative}", _git_mode_kind(mode))
    if len(observed.occupied) > before:
        # An occupied surface is brownfield outright, exactly as in the working tree, so the
        # emptiness report below is not produced. Dropping the walk's failures here is safe in
        # ONE direction only, which is the direction that matters: every dropped failure could
        # merely have added another reason NOT to be greenfield, and greenfield is already
        # unreachable once anything is occupied. It is an evidence-completeness trade, not a
        # verdict that can come out more permissive than what was observed.
        return
    for failure in failures:
        observed.ambiguous(KIND_TREE, failure)
    unexpected = sorted(name for name, mode in root if not _is_allowlisted_committed_entry(name, mode))
    if unexpected:
        shown = ", ".join(unexpected[:MAX_NAMED_ENTRIES])
        suffix = "" if len(unexpected) <= MAX_NAMED_ENTRIES else f" (+{len(unexpected) - MAX_NAMED_ENTRIES} more)"
        observed.ambiguous(KIND_TREE, f"HEAD carries {len(unexpected)} entries outside the allowlist: {shown}{suffix}")


def _commit_tree_oid(lines: list[bytes]) -> str | None:
    """The tree id from a commit's first header line, or None when it is not exactly that."""
    if not lines or not lines[0].startswith(b"tree "):
        return None
    text = lines[0][len(b"tree ") :].decode("ascii", "replace").strip()
    return text if _is_object_id(text) else None


def prove_single_commit(git_fd: int, oid: str, observed: Observation) -> None:
    """Prove HEAD is one parentless commit with an empty tree, or name why the proof failed."""
    try:
        parsed = read_loose_object(git_fd, oid)
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_HISTORY, f"commit {oid} is not readable: {_detail(exc)}")
        return
    if parsed is None:
        # Packed history, a dangling ref, or an alternate object store. Walking a packfile means
        # idx parsing and delta resolution, which this module does not do, and the other two are
        # not readable here at all; refusing is the conservative half of that trade. The three are
        # named together because the file's absence cannot tell them apart.
        observed.ambiguous(KIND_HISTORY, f"commit {oid} is not a loose object; packed, absent, and alternate objects are not walked offline")
        return
    kind, body = parsed
    if kind != "commit":
        observed.ambiguous(KIND_HISTORY, f"{oid} is not a commit object")
        return
    headers, _, _ = body.partition(b"\n\n")
    lines = headers.split(b"\n")
    parents = [line for line in lines if line.startswith(b"parent ")]
    if parents:
        observed.ambiguous(KIND_HISTORY, f"commit {oid} has {len(parents)} parent commit(s)")
    tree_oid = _commit_tree_oid(lines)
    if tree_oid is None:
        # Without a tree id there is nothing to prove empty, and assuming empty is the defect.
        observed.ambiguous(KIND_HISTORY, f"commit {oid} does not name a tree in its first header")
        return
    # Run even when the commit has parents: an occupied surface in the committed tree is a
    # positive observation worth naming, and brownfield outranks the parent ambiguity.
    prove_committed_tree_is_empty(git_fd, tree_oid, observed)


def _first_evidence_of_objects(git_fd: int) -> str | None:
    """One named piece of evidence that `.git/objects` holds anything, or None when it is empty.

    Bounded and read-only: at most `MAX_OBJECT_STORE_ENTRIES` names at the top of `.git/objects`
    plus one listing per subdirectory, stopping at the FIRST evidence rather than inventorying.
    `git init` leaves `objects/info` and `objects/pack` present and EMPTY, so a directory is not
    evidence -- its contents are.
    """
    with _descend(git_fd, ("objects",)) as objects_fd:
        names = sorted(os.listdir(objects_fd))
        if len(names) > MAX_OBJECT_STORE_ENTRIES:
            raise MalformedObject(f"{GIT_DIRECTORY_NAME}/objects holds more than {MAX_OBJECT_STORE_ENTRIES} entries")
        for name in names:
            info = os.stat(name, dir_fd=objects_fd, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                return f"{GIT_DIRECTORY_NAME}/objects/{name} is a {_node_kind(info.st_mode)}"
            try:
                with _descend(objects_fd, (name,)) as child_fd:
                    inner = sorted(os.listdir(child_fd))
            except FileNotFoundError as exc:
                # Raised as UNDETERMINED so the caller's "objects is absent" branch stays about
                # `objects` itself and cannot absorb a subdirectory that moved mid-read.
                raise UndeterminedPath(f"{GIT_DIRECTORY_NAME}/objects/{name} changed while it was read") from exc
            if inner:
                shown = ", ".join(inner[:MAX_NAMED_ENTRIES])
                suffix = "" if len(inner) <= MAX_NAMED_ENTRIES else f" (+{len(inner) - MAX_NAMED_ENTRIES} more)"
                return f"{GIT_DIRECTORY_NAME}/objects/{name} is not empty: {shown}{suffix}"
    return None


def prove_no_history_exists(git_fd: int, branch: str, observed: Observation) -> None:
    """Prove an UNBORN branch sits in a repository that has no history AT ALL.

    A branch absent from both ref storages is the one place where absence is supposed to be a
    proof, and on disk it is indistinguishable from a branch that was deleted, renamed, or
    packed into a storage this module could not read. `git init && git commit && git update-ref -d
    refs/heads/main` left seven objects and a reflog behind and was reported greenfield with zero
    ambiguities, and so was a packed repository whose `packed-refs` had been emptied.

    So the ONLY unborn branch that earns greenfield is one in a repository whose object store and
    reflog are both empty, which is exactly the shape `git init` leaves. Anything else is named:
    a staged blob, an unreferenced pack, a `commit-graph`, or a reflog entry each mean something
    already happened here, and greenfield is the verdict that would authorize writing a baseline
    over it.
    """
    try:
        evidence = _first_evidence_of_objects(git_fd)
    except FileNotFoundError as exc:
        # A Git directory with no object store at all is malformed, not proof of emptiness -- and
        # an `objects` path that is a plain file is a different malformation, named as itself.
        malformed = _malformed_directory(exc, "objects")
        observed.ambiguous(KIND_HISTORY, malformed or f"{branch} is unborn and {GIT_DIRECTORY_NAME}/objects is absent")
        return
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_HISTORY, f"{GIT_DIRECTORY_NAME}/objects is not readable: {_detail(exc)}")
        return
    if evidence is not None:
        observed.ambiguous(KIND_HISTORY, f"{branch} is unborn but {evidence}")
    try:
        with _descend(git_fd, ("logs",)) as logs_fd:
            logs = sorted(os.listdir(logs_fd))
    except FileNotFoundError as exc:
        # `git init` writes no reflog, so an absent `logs` is the expected shape.
        malformed = _malformed_directory(exc, "logs")
        if malformed is not None:
            observed.ambiguous(KIND_HISTORY, malformed)
        return
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_HISTORY, f"{GIT_DIRECTORY_NAME}/logs is not readable: {_detail(exc)}")
        return
    if logs:
        shown = ", ".join(logs[:MAX_NAMED_ENTRIES])
        suffix = "" if len(logs) <= MAX_NAMED_ENTRIES else f" (+{len(logs) - MAX_NAMED_ENTRIES} more)"
        observed.ambiguous(KIND_HISTORY, f"{branch} is unborn but {GIT_DIRECTORY_NAME}/logs is not empty: {shown}{suffix}")


def name_unwalked_packed_objects(git_fd: int, observed: Observation) -> None:
    """Name a packfile, because the commit walk reads LOOSE objects only.

    A resolved single parentless commit proves what THAT commit reaches, not what the repository
    holds, and the object-store proof above guards only the UNBORN branch. `git gc` followed by
    `git commit --amend` leaves the amended commit loose and parentless while the previous history
    sits in `objects/pack`: every step of the single-commit proof succeeds and reports nothing, and
    the repository comes out greenfield with a whole history this module never read. `git init`
    leaves `objects/pack` present and EMPTY, and `git pack-refs` does not touch it, so the ordinary
    greenfield shapes stay greenfield.
    """
    try:
        with _descend(git_fd, ("objects", "pack")) as pack_fd:
            names = sorted(os.listdir(pack_fd))
    except FileNotFoundError as exc:
        malformed = _malformed_directory(exc, "objects/pack")
        if malformed is not None:
            observed.ambiguous(KIND_HISTORY, malformed)
        return
    except READ_FAILURES as exc:
        observed.ambiguous(KIND_HISTORY, f"{GIT_DIRECTORY_NAME}/objects/pack is not readable: {_detail(exc)}")
        return
    if names:
        shown = ", ".join(names[:MAX_NAMED_ENTRIES])
        suffix = "" if len(names) <= MAX_NAMED_ENTRIES else f" (+{len(names) - MAX_NAMED_ENTRIES} more)"
        observed.ambiguous(KIND_HISTORY, f"{GIT_DIRECTORY_NAME}/objects/pack is not empty, so commits this walk did not read may exist: {shown}{suffix}")


def prove_empty_history(git_fd: int, observed: Observation) -> None:
    """Prove the repository holds no commit beyond an initial one, or name the ambiguity.

    The three outcomes of `resolve_sole_ref` get three different branches here, and the middle
    one -- undetermined -- is the branch that used to be missing.
    """
    branch = read_head_branch(git_fd, observed)
    if branch is None:
        return  # `read_head_branch` named the head-form ambiguity.
    before = len(observed.ambiguities)
    state, oid = resolve_sole_ref(git_fd, branch, observed)
    if state == REF_UNDETERMINED:
        if len(observed.ambiguities) == before:
            # Defence in depth against this ticket's own defect class: an undetermined ref
            # surface that named NOTHING would read as a clean, silent greenfield. Every
            # `REF_UNDETERMINED` return above names its reason, so this line should be
            # unreachable -- and it is here because two fixes in this family have each
            # reintroduced the bug they closed, one link away.
            observed.ambiguous(KIND_REFS, f"{branch} could not be resolved and no reason was recorded")
        return
    if state == REF_UNBORN:
        prove_no_history_exists(git_fd, branch, observed)
        return
    if oid is None:
        # Named rather than asserted: an `assert` would strip under `-O` and a crash would lose
        # the JSON result entirely, and a resolved ref with no id is still not an absent commit.
        observed.ambiguous(KIND_REFS, f"{branch} resolved without an object id")
        return
    name_unwalked_packed_objects(git_fd, observed)
    prove_single_commit(git_fd, oid, observed)


def open_git_directory(target_fd: int) -> int:
    """Open `.git`, refusing anything that is not a directory inside this checkout.

    A `.git` FILE is a linked-worktree or submodule `gitdir:` redirect and a `.git` SYMLINK
    points at another tree. Following either would classify a repository other than the one
    the caller named, so both are clean refusals rather than silent redirection.
    """
    try:
        info = os.stat(GIT_DIRECTORY_NAME, dir_fd=target_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise InspectionRefusal(f"target is not a Git repository: {GIT_DIRECTORY_NAME} is absent") from None
    except OSError as exc:
        raise InspectionRefusal(f"cannot inspect {GIT_DIRECTORY_NAME}: {_errno_name(exc)}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise InspectionRefusal(f"{GIT_DIRECTORY_NAME} is a symlink, so it names another checkout")
    if not stat.S_ISDIR(info.st_mode):
        raise InspectionRefusal(f"{GIT_DIRECTORY_NAME} is not a directory ({_node_kind(info.st_mode)}), so it is a redirect")
    try:
        return _open_at(GIT_DIRECTORY_NAME, target_fd, directory=True)
    except OSError as exc:
        raise InspectionRefusal(f"cannot open {GIT_DIRECTORY_NAME}: {_errno_name(exc)}") from exc


def _result(status: str, target: Path, *, verdict: str | None, observed: Observation | None, reasons: list[str], code: int) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "command": "classify",
        "status": status,
        "exit_code": code,
        "target": str(target),
        "verdict": verdict,
        "occupied": [] if observed is None else observed.sorted_occupied(),
        "ambiguities": [] if observed is None else observed.sorted_ambiguities(),
        "reasons": reasons,
    }


def classify(target: Path) -> Observation:
    """Gather every observation for one repository. Writes nothing and runs no subprocess."""
    observed = Observation()
    try:
        target_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except FileNotFoundError:
        raise InspectionRefusal("target does not exist") from None
    except OSError as exc:
        raise InspectionRefusal(f"cannot open target: {_errno_name(exc)}") from exc
    try:
        git_fd = open_git_directory(target_fd)
        try:
            scan_candidates(target_fd, observed)
            scan_git_hooks(git_fd, observed)
            if observed.occupied:
                # An occupied surface is brownfield outright (ADR-0022 decision 4). The
                # emptiness proof below only serves greenfield, so it is not run.
                return observed
            scan_content(target_fd, observed)
            prove_empty_history(git_fd, observed)
            return observed
        finally:
            os.close(git_fd)
    finally:
        os.close(target_fd)


def classify_command(target: Path) -> tuple[dict[str, Any], int]:
    """Classify one repository and return the canonical result plus its exit code."""
    target = Path(target)
    try:
        if not target.is_absolute():
            raise InspectionRefusal("target must be an absolute path", INVALID_INPUT_CODE)
        observed = classify(target)
    except InspectionRefusal as exc:
        return _result("refused", target, verdict=None, observed=None, reasons=[exc.reason], code=exc.code), exc.code
    return _result("classified", target, verdict=observed.verdict(), observed=observed, reasons=[], code=0), 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify a repository as greenfield, brownfield, or refuse-and-ask. Evidence only: this reports what is on disk and never claims activation is permitted."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("classify")
    command.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)
    result, code = classify_command(args.target)
    sys.stdout.buffer.write(canonical_bytes(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
