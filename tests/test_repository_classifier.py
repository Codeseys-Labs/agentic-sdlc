"""Tests for the three-way greenfield/brownfield/refuse-and-ask classifier.

Every negative assertion here carries a POSITIVE CONTROL in the same test: the shape that
should produce the opposite verdict is built by the same helpers in the same temporary
directory, so a refusal cannot come from a decoy that was never created. That discipline is
not decoration -- a symlink test elsewhere in this repository pointed at a path it never
made, so its "refusal" was ENOENT rather than the guard it named.

The repositories are hand-built rather than produced by `git init`, so the suite needs no
`git` binary and can construct shapes a real client will not make on demand (a packed-refs
branch with no loose ref, a reftable backend, a symlinked `.git`). Real `git init` shapes are
covered by the execution evidence in the change report, not here.
"""
from __future__ import annotations

import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import os
import signal
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "agentic-sdlc" / "tools" / "repository-classifier.py"

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

GIT_OBJECTS = ".git/objects"
GIT_LOGS = ".git/logs"
GIT_REFS = ".git/refs"


def _load():
    spec = importlib.util.spec_from_file_location("_agentic_sdlc_repository_classifier", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rc = _load()


TREE_MODE = 0o40000
BLOB_MODE = 0o100644
GITLINK_MODE = 0o160000
SYMLINK_MODE = 0o120000


class BlockedOpen(BaseException):
    """Raised by the FIFO watchdog below, and deliberately NOT an `OSError`.

    The classifier turns every `OSError` into a named ambiguity, so an `OSError`-shaped watchdog
    (`TimeoutError` is one) gets absorbed as one and the failure then describes an unreadable file
    instead of the blocked open that actually happened. A `BaseException` escapes both the module's
    `READ_FAILURES` clauses and its `except InspectionRefusal`, and `unittest` still reports it as
    an ordinary error.
    """


def write_raw_object(git: Path, payload: bytes) -> str:
    """Write one loose object whose header the caller controls byte for byte."""
    oid = hashlib.sha1(payload, usedforsecurity=False).hexdigest()
    directory = git / "objects" / oid[:2]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / oid[2:]).write_bytes(zlib.compress(payload))
    return oid


def write_object(git: Path, kind: bytes, body: bytes) -> str:
    """Write one loose object with a correct type/size header and return its object id."""
    return write_raw_object(git, kind + b" " + str(len(body)).encode() + b"\0" + body)


def write_unterminated_object(git: Path, kind: bytes, body: bytes) -> str:
    """Write one loose object whose zlib stream never ENDS, as a truncated write leaves it.

    `Z_SYNC_FLUSH` makes every payload byte inflatable while the end-of-stream marker is never
    written, which is the only input that separates the two halves of the inflation guard: the
    oversized case leaves an unconsumed tail, and this one leaves none.
    """
    payload = kind + b" " + str(len(body)).encode() + b"\0" + body
    oid = hashlib.sha1(payload, usedforsecurity=False).hexdigest()
    engine = zlib.compressobj()
    directory = git / "objects" / oid[:2]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / oid[2:]).write_bytes(engine.compress(payload) + engine.flush(zlib.Z_SYNC_FLUSH))
    return oid


def object_path(git: Path, oid: str) -> Path:
    return git / "objects" / oid[:2] / oid[2:]


def write_commit(git: Path, *, parents: tuple[str, ...] = (), tree: str = EMPTY_TREE) -> str:
    """Write one loose commit object and return its object id."""
    body = f"tree {tree}\n".encode()
    for parent in parents:
        body += f"parent {parent}\n".encode()
    body += b"author A <a@example.invalid> 0 +0000\ncommitter A <a@example.invalid> 0 +0000\n\nc\n"
    return write_object(git, b"commit", body)


def write_blob(git: Path, data: bytes = b"x\n") -> str:
    return write_object(git, b"blob", data)


def write_tree(git: Path, entries: dict[str, tuple[int, str]]) -> str:
    """Write one loose tree object from `{name: (mode, oid)}` and return its object id."""
    body = b""
    for name in sorted(entries):
        mode, oid = entries[name]
        body += f"{mode:o} {name}".encode() + b"\0" + bytes.fromhex(oid)
    return write_object(git, b"tree", body)


def build_tree(git: Path, paths: dict[str, tuple[int, str]]) -> str:
    """Build nested loose trees for POSIX-relative `paths` and return the ROOT tree's id.

    A path with a `/` creates the intermediate trees Git would create, so a test can commit
    `.github/workflows/ci.yml` and exercise the classifier's prefix-directed descent.
    """
    here: dict[str, tuple[int, str]] = {}
    below: dict[str, dict[str, tuple[int, str]]] = {}
    for relative, value in paths.items():
        head, _, rest = relative.partition("/")
        if rest:
            below.setdefault(head, {})[rest] = value
        else:
            here[head] = value
    for name, nested in below.items():
        here[name] = (TREE_MODE, build_tree(git, nested))
    return write_tree(git, here)


def make_git(root: Path, *, head: str = "ref: refs/heads/main\n", samples: bool = True) -> Path:
    """Build the `.git` directory a fresh `git init` leaves behind."""
    git = root / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "refs" / "tags").mkdir(parents=True)
    (git / "objects" / "info").mkdir(parents=True)
    hooks = git / "hooks"
    hooks.mkdir()
    if samples:
        (hooks / "pre-commit.sample").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (git / "HEAD").write_text(head, encoding="utf-8")
    (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    return git


def snapshot(root: Path) -> dict[str, tuple[int, int, int]]:
    """Names, modes, sizes, and nanosecond mtimes of every node under `root`."""
    seen: dict[str, tuple[int, int, int]] = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        seen[str(path.relative_to(root))] = (info.st_mode, info.st_size, info.st_mtime_ns)
    return seen


class ClassifierTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_root = Path(self.tmp.name)

    def repo(self, name: str, *, commit: bool = False, readme: bool = False, **kwargs) -> Path:
        """A repository that classifies greenfield until the caller occupies something."""
        target = self.tmp_root / name
        target.mkdir()
        git = make_git(target, **kwargs)
        if commit:
            oid = write_commit(git)
            (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        if readme:
            (target / "README.md").write_text("# intent\n", encoding="utf-8")
        return target

    def commit_tree(self, target: Path, tree: str, *, parents: tuple[str, ...] = ()) -> str:
        """Point the only branch at one commit carrying `tree`, and return the commit id."""
        git = target / ".git"
        oid = write_commit(git, tree=tree, parents=parents)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        return oid

    def committed(self, name: str, *relatives: str, mode: int = BLOB_MODE) -> Path:
        """A repository whose HEAD commit CARRIES `relatives` and whose checkout shows nothing.

        This is the reviewer's reproduction shape: `git add`, `git commit`, then remove the
        files from the working tree. The classifier must still see the surfaces.
        """
        target = self.tmp_root / name
        target.mkdir()
        git = make_git(target)
        blob = write_blob(git)
        self.commit_tree(target, build_tree(git, {relative: (mode, blob) for relative in relatives}))
        return target

    def unpack_branch(self, target: Path) -> str:
        """Remove the only loose branch and return its object id, as `git pack-refs --all` does."""
        branch = target / ".git" / "refs" / "heads" / "main"
        oid = branch.read_text(encoding="utf-8").strip()
        branch.unlink()
        return oid

    def write_packed_refs(self, target: Path, *lines: str) -> None:
        """Write `.git/packed-refs` with Git's own header and the caller's exact body lines."""
        body = "".join(f"{line}\n" for line in ("# pack-refs with: peeled fully-peeled sorted ", *lines))
        (target / ".git" / "packed-refs").write_text(body, encoding="utf-8")

    def classify(self, target: Path) -> dict:
        result, code = rc.classify_command(target)
        self.assertEqual(code, result["exit_code"], result)
        return result

    def classify_bounded(self, target: Path, *, seconds: float = 10.0) -> dict:
        """`classify` under a watchdog, so a blocking `open` FAILS instead of stalling the suite.

        Every FIFO fixture here exists to prove the opener never blocks, and without this the proof
        has no failure a reader can attribute: dropping `O_NONBLOCK` simply stops the process, with
        no assertion, no ambiguity and no named guard. The interval timer turns the one
        unattributable outcome in this file into an ordinary error that says which flag was lost.
        """
        if not hasattr(signal, "setitimer"):  # pragma: no cover - POSIX hosts have one
            return self.classify(target)

        def stalled(_signum, _frame):
            raise BlockedOpen(f"classification blocked for {seconds}s, so an opener lost O_NONBLOCK")

        previous = signal.signal(signal.SIGALRM, stalled)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return self.classify(target)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)

    def assertVerdictWithoutBlocking(self, target: Path, verdict: str) -> dict:
        result = self.classify_bounded(target)
        self.assertEqual(result["status"], "classified", result)
        self.assertEqual(result["verdict"], verdict, result)
        return result

    def assertVerdict(self, target: Path, verdict: str) -> dict:
        result = self.classify(target)
        self.assertEqual(result["status"], "classified", result)
        self.assertEqual(result["exit_code"], 0, result)
        self.assertEqual(result["verdict"], verdict, result)
        return result

    def assertOccupied(self, result: dict, surface: str, path: str) -> None:
        self.assertTrue(
            any(item["surface"] == surface and item["path"] == path for item in result["occupied"]),
            f"expected occupied {surface} at {path}, got {result['occupied']}",
        )

    def assertAmbiguity(self, result: dict, kind: str, fragment: str) -> None:
        """Assert WHICH observation was ambiguous. A bare refuse-and-ask tells the human
        nothing, and every ambiguity would otherwise be an identical verdict string."""
        self.assertTrue(
            any(item["kind"] == kind and fragment in item["detail"] for item in result["ambiguities"]),
            f"expected a {kind} ambiguity naming {fragment!r}, got {result['ambiguities']}",
        )

    def assertRefusedToInspect(self, target: Path, fragment: str) -> dict:
        result, code = rc.classify_command(target)
        self.assertEqual(result["status"], "refused", result)
        self.assertEqual(code, rc.INSPECT_REFUSAL_CODE, result)
        self.assertIsNone(result["verdict"], result)
        self.assertTrue(
            any(fragment in reason for reason in result["reasons"]),
            f"expected a reason containing {fragment!r}, got {result['reasons']}",
        )
        return result


class GreenfieldTests(ClassifierTestCase):
    def test_initialized_repository_with_no_commit_is_greenfield(self) -> None:
        target = self.repo("fresh")

        result = self.assertVerdict(target, "greenfield")

        self.assertEqual(result["occupied"], [])
        self.assertEqual(result["ambiguities"], [])

    def test_single_parentless_commit_with_readme_is_greenfield(self) -> None:
        target = self.repo("initial", commit=True, readme=True)

        result = self.assertVerdict(target, "greenfield")

        self.assertEqual(result["ambiguities"], [])

    def test_sample_hooks_alone_are_not_an_occupied_hook_surface(self) -> None:
        occupied = self.repo("hooked", commit=True)
        (occupied / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")

        result = self.assertVerdict(occupied, "brownfield")
        self.assertOccupied(result, "hook", ".git/hooks/pre-commit")

        # Positive control: the same builder with only the `.sample` file must not report a
        # hook, or the assertion above would pass for a repository that has no real hook.
        self.assertVerdict(self.repo("samples-only", commit=True), "greenfield")


class BrownfieldTests(ClassifierTestCase):
    def occupy(self, name: str, relative: str, *, directory: bool = False) -> Path:
        target = self.repo(name, commit=True, readme=True)
        node = target / relative
        node.parent.mkdir(parents=True, exist_ok=True)
        if directory:
            node.mkdir()
        else:
            node.write_text("x\n", encoding="utf-8")
        return target

    def assertOccupiedSurface(self, name: str, relative: str, surface: str, *, directory: bool = False) -> None:
        target = self.occupy(name, relative, directory=directory)

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, surface, relative)
        self.assertNotEqual(result["verdict"], "greenfield", result)
        # Positive control: the identical repository without that one node is greenfield, so
        # the brownfield verdict above is attributable to the node and nothing else.
        self.assertVerdict(self.repo(f"{name}-control", commit=True, readme=True), "greenfield")

    def test_gitlab_ci_repository_is_never_greenfield(self) -> None:
        self.assertOccupiedSurface("gitlab", ".gitlab-ci.yml", "ci")

    def test_jenkins_repository_is_never_greenfield(self) -> None:
        self.assertOccupiedSurface("jenkins", "Jenkinsfile", "ci")

    def test_buildkite_repository_is_never_greenfield(self) -> None:
        self.assertOccupiedSurface("buildkite", ".buildkite", "ci", directory=True)

    def test_woodpecker_repository_is_never_greenfield(self) -> None:
        self.assertOccupiedSurface("woodpecker", ".woodpecker.yml", "ci")

    def test_github_workflows_is_an_occupied_ci_surface(self) -> None:
        self.assertOccupiedSurface("gha", ".github/workflows", "ci", directory=True)

    def test_agents_md_is_an_occupied_guidance_surface(self) -> None:
        self.assertOccupiedSurface("guided", "AGENTS.md", "guidance")

    def test_seeds_is_an_occupied_queue_surface(self) -> None:
        self.assertOccupiedSurface("queued", ".seeds", "queue", directory=True)

    def test_docs_adr_is_an_occupied_decision_surface(self) -> None:
        self.assertOccupiedSurface("decided", "docs/adr", "decision", directory=True)

    def test_mise_toml_is_an_occupied_toolchain_surface(self) -> None:
        self.assertOccupiedSurface("pinned", "mise.toml", "toolchain")

    def test_lefthook_is_an_occupied_hook_surface(self) -> None:
        self.assertOccupiedSurface("hooks", "lefthook.yml", "hook")

    def test_activation_state_root_is_an_occupied_contract_surface(self) -> None:
        self.assertOccupiedSurface("activated", ".agentic-sdlc", "contract", directory=True)

    def test_occupied_surface_outranks_content_that_would_otherwise_be_ambiguous(self) -> None:
        """An occupied surface decides brownfield outright, so the emptiness proof -- which
        only ever serves greenfield -- is not run and reports nothing that could be misread
        as blocking the verdict."""
        target = self.repo("mixed", commit=True, readme=True)
        (target / "src").mkdir()
        (target / "AGENTS.md").write_text("# policy\n", encoding="utf-8")

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, "guidance", "AGENTS.md")
        self.assertEqual(result["ambiguities"], [], result)
        # Positive control: without the guidance file the very same `src` directory IS an
        # ambiguity, so the empty list above is the short circuit and not a broken channel.
        (target / "AGENTS.md").unlink()
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "unclassified-content", "src")

    def test_symlinked_guidance_file_still_occupies_the_surface(self) -> None:
        target = self.repo("linked-guidance", commit=True, readme=True)
        outside = self.tmp_root / "elsewhere.md"
        outside.write_text("# foreign policy\n", encoding="utf-8")
        (target / "AGENTS.md").symlink_to(outside)

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, "guidance", "AGENTS.md")
        self.assertTrue(any(item["kind"] == "symlink" for item in result["occupied"]), result["occupied"])

    def test_a_fifo_candidate_is_reported_without_being_opened(self) -> None:
        target = self.repo("fifo", commit=True, readme=True)
        os.mkfifo(target / "AGENTS.md")

        # A candidate is never OPENED, only stat-ed, so a FIFO at one cannot block this process --
        # and the watchdog makes that a named failure rather than a stalled suite.
        result = self.assertVerdictWithoutBlocking(target, "brownfield")

        self.assertOccupied(result, "guidance", "AGENTS.md")
        self.assertTrue(any(item["kind"] == "other" for item in result["occupied"]), result["occupied"])


class AmbiguityTests(ClassifierTestCase):
    def test_unclassified_top_level_content_is_refuse_and_ask(self) -> None:
        target = self.repo("contentful", commit=True, readme=True)
        (target / "src").mkdir()
        (target / "main.c").write_text("int main(void){return 0;}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "main.c")
        self.assertAmbiguity(result, "unclassified-content", "src")
        # Positive control: the allowlisted subset alone is greenfield, so the ambiguity is
        # caused by the two added entries rather than by the allowlist refusing everything.
        self.assertVerdict(self.repo("contentful-control", commit=True, readme=True), "greenfield")

    def test_a_second_commit_is_refuse_and_ask(self) -> None:
        target = self.repo("history", readme=True)
        git = target / ".git"
        first = write_commit(git)
        second = write_commit(git, parents=(first,))
        (git / "refs" / "heads" / "main").write_text(f"{second}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "parent")
        # Positive control: repointing the same branch at the parentless commit through the
        # same channel is greenfield, so the ambiguity is the parent header and not the
        # mere presence of a commit.
        (git / "refs" / "heads" / "main").write_text(f"{first}\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_packed_branch_is_not_mistaken_for_an_unborn_branch(self) -> None:
        target = self.repo("packed", readme=True)
        git = target / ".git"
        oid = write_commit(git)
        (git / "objects" / oid[:2] / oid[2:]).unlink()
        (git / "packed-refs").write_text(f"# pack-refs with: peeled\n{oid} refs/heads/main\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", oid)
        # Positive control: without the packed-refs file the identical tree has an unborn
        # branch and is greenfield, so the refusal comes from resolving the packed branch
        # rather than from anything else this repository contains.
        (git / "packed-refs").unlink()
        self.assertVerdict(target, "greenfield")

    def test_another_ref_is_refuse_and_ask(self) -> None:
        target = self.repo("tagged", commit=True, readme=True)
        git = target / ".git"
        (git / "refs" / "tags" / "v1").write_text(f"{'0' * 40}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "refs/tags/v1")
        (git / "refs" / "tags" / "v1").unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_packed_foreign_ref_is_refuse_and_ask(self) -> None:
        target = self.repo("packed-foreign", commit=True, readme=True)
        git = target / ".git"
        (git / "packed-refs").write_text(f"{'0' * 40} refs/remotes/origin/main\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "refs/remotes/origin/main")
        (git / "packed-refs").unlink()
        self.assertVerdict(target, "greenfield")

    def test_detached_head_is_refuse_and_ask(self) -> None:
        target = self.repo("detached", readme=True, head=f"{'0' * 40}\n")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "head-form", "HEAD")
        # Positive control: the same tree with a branch symref HEAD is greenfield.
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_head_this_module_cannot_name_stops_the_ref_walk(self) -> None:
        """The proof returns the moment HEAD cannot be reduced to one branch NAME. Walking on
        without one resolves a nameless branch and then reports it unborn against an object store
        that plainly holds commits -- evidence about a branch nobody named."""
        target = self.repo("unnamed-head", commit=True, readme=True, head=f"{'0' * 40}\n")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertEqual(
            result["ambiguities"],
            [{"detail": ".git/HEAD is not a branch symref", "kind": "head-form"}],
            "a HEAD with no branch name is the ONLY thing this repository can report",
        )
        # Positive control: a branch symref in the same file resolves the same commit and is
        # greenfield, so the single ambiguity above is the HEAD form and not a walk that never runs.
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_reftable_backend_is_refuse_and_ask(self) -> None:
        target = self.repo("reftable", commit=True, readme=True)
        (target / ".git" / "reftable").mkdir()

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "reftable")
        (target / ".git" / "reftable").rmdir()
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_parent_is_not_followed_out_of_the_repository(self) -> None:
        target = self.repo("escape", commit=True, readme=True)
        outside = self.tmp_root / "outside-github"
        (outside / "workflows").mkdir(parents=True)
        (outside / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
        (target / ".github").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "undetermined-surface", ".github/workflows")
        self.assertEqual(result["occupied"], [], result)
        # The decoy exists and is a real occupied CI surface when it is INSIDE the
        # repository, so the ambiguity above is the symlink guard and not ENOENT.
        control = self.repo("escape-control", commit=True, readme=True)
        (control / ".github" / "workflows").mkdir(parents=True)
        (control / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
        self.assertOccupied(self.assertVerdict(control, "brownfield"), "ci", ".github/workflows")
        self.assertTrue((outside / "workflows" / "ci.yml").is_file())

    def test_a_non_directory_component_is_a_conclusive_absence(self) -> None:
        """The distinguishing input for the component classifier. Linux answers ENOTDIR for
        BOTH a plain file and a symlink-to-directory under `O_NOFOLLOW | O_DIRECTORY`, so the
        errno alone cannot separate them -- and reading the symlink case as absence is what
        would let a redirected subtree earn greenfield."""
        target = self.repo("filecomponent", commit=True, readme=True)
        (target / "docs").write_text("not a directory\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "docs")
        self.assertFalse(
            any(item["kind"] == "undetermined-surface" for item in result["ambiguities"]),
            f"a plain file component is a conclusive absence, got {result['ambiguities']}",
        )
        # Positive control: replacing that file with a symlink to a real directory, through
        # the same channel, DOES make the same candidate undetermined.
        (target / "docs").unlink()
        elsewhere = self.tmp_root / "outside-docs"
        (elsewhere / "adr").mkdir(parents=True)
        (target / "docs").symlink_to(elsewhere, target_is_directory=True)
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "undetermined-surface", "docs/adr")

    def test_a_component_that_disappears_mid_check_is_a_conclusive_absence(self) -> None:
        """The deliberate asymmetry, from the other side. A component that is gone by the time it is
        stat-ed makes a CANDIDATE conclusively absent -- nothing can be at a path that no longer
        exists -- while the identical race under `.git/refs` stays UNDETERMINED, because "no loose
        refs" read off a vanished directory is a claim about refs this module never saw. Patched,
        because a real race cannot be scheduled."""
        target = self.repo("racing-component", commit=True, readme=True)
        (target / "docs").write_text("not a directory\n", encoding="utf-8")
        real_stat = os.stat

        def stat_where_docs_has_vanished(path, *args, **kwargs):
            if path == "docs":
                raise FileNotFoundError(errno.ENOENT, "the component was removed after its open failed")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(rc.os, "stat", stat_where_docs_has_vanished):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "docs")
        self.assertFalse(
            any(item["kind"] == "undetermined-surface" for item in result["ambiguities"]),
            f"a path that no longer exists cannot hold a candidate: {result['ambiguities']}",
        )
        # Positive control: the same `docs/adr` as a real readable directory IS a named occupied
        # decision surface, so the silence above is the conclusive absence and not a dead channel.
        (target / "docs").unlink()
        (target / "docs" / "adr").mkdir(parents=True)
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "decision", "docs/adr")

    def test_the_occupied_kind_names_what_the_node_actually_is(self) -> None:
        """`kind` is the whole evidence value of an occupied record: `directory` and `file` at the
        same path are different findings for whoever has to answer the question."""
        target = self.repo("kinds", commit=True, readme=True)
        (target / ".seeds").mkdir()
        (target / "AGENTS.md").write_text("# policy\n", encoding="utf-8")

        result = self.assertVerdict(target, "brownfield")

        kinds = {item["path"]: item["kind"] for item in result["occupied"]}
        self.assertEqual(kinds[".seeds"], "directory", result["occupied"])
        self.assertEqual(kinds["AGENTS.md"], "file", result["occupied"])
        # Positive control on the committed side, through the tree walk's own mode reader.
        committed = self.assertVerdict(self.committed("kinds-committed", "docs/adr/0001-x.md"), "brownfield")
        self.assertEqual(
            {item["path"]: item["kind"] for item in committed["occupied"]}["HEAD:docs/adr"], "directory", committed["occupied"]
        )

    def test_the_named_hook_list_is_bounded_at_the_shared_evidence_ceiling(self) -> None:
        """One hook is not the evidence; the bound is. A tighter list would hide installed hooks
        behind a brownfield verdict that names only the first of them."""
        target = self.repo("many-hooks", commit=True, readme=True)
        for index in range(rc.MAX_NAMED_ENTRIES + 2):
            (target / ".git" / "hooks" / f"hook{index:03d}").write_text("#!/bin/sh\n", encoding="utf-8")

        result = self.assertVerdict(target, "brownfield")

        self.assertEqual(len(result["occupied"]), rc.MAX_NAMED_ENTRIES, result["occupied"])
        self.assertOccupied(result, "hook", f".git/hooks/hook{rc.MAX_NAMED_ENTRIES - 1:03d}")
        # Positive control: the same builder with two hooks names BOTH, so the ceiling above is the
        # bound and not a reader that only ever reports one.
        control = self.repo("two-hooks", commit=True, readme=True)
        for name in ("pre-commit", "pre-push"):
            (control / ".git" / "hooks" / name).write_text("#!/bin/sh\n", encoding="utf-8")
        second = self.assertVerdict(control, "brownfield")
        self.assertOccupied(second, "hook", ".git/hooks/pre-commit")
        self.assertOccupied(second, "hook", ".git/hooks/pre-push")

    def test_a_symlinked_git_refs_directory_is_not_read_through(self) -> None:
        target = self.repo("linked-refs", readme=True)
        git = target / ".git"
        outside = self.tmp_root / "outside-refs"
        (outside / "heads").mkdir(parents=True)
        oid = write_commit(git)
        (outside / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        for child in sorted((git / "refs").rglob("*"), reverse=True):
            child.rmdir()
        (git / "refs").rmdir()
        (git / "refs").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "refs is a symlink")
        # The decoy is a complete, readable ref pointing at a real parentless commit -- the
        # same shape that is greenfield when it lives INSIDE `.git` -- so the ambiguity is
        # the custody guard and not an unreadable or absent decoy.
        (git / "refs").unlink()
        (git / "refs" / "heads").mkdir(parents=True)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_object_directory_is_not_read_through(self) -> None:
        """A multi-component path handed to ONE `openat` protects only its last component, so
        `objects/ab/cdef...` would be read through a symlinked `objects` -- and a parentless
        commit fetched from outside the repository would earn greenfield."""
        target = self.repo("linked-objects", readme=True)
        git = target / ".git"
        oid = write_commit(git)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        outside = self.tmp_root / "outside-objects"
        (git / "objects").rename(outside)
        (git / "objects").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "objects is a symlink")
        # The decoy holds the real parentless commit that IS greenfield when the same bytes
        # sit inside `.git`, so the ambiguity is the custody guard and not a missing object.
        (git / "objects").unlink()
        outside.rename(git / "objects")
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_object_fanout_directory_is_not_read_through(self) -> None:
        """The one shape that can OBSERVE `_read_small`'s per-component descent, which is what the
        module's whole containment argument rests on.

        The test above symlinks `objects` itself, and `name_unwalked_packed_objects` refuses that
        independently through `_descend`, so it stays refuse-and-ask -- with the same detail -- even
        when the descent is replaced by a single whole-path `openat`. A symlinked FANOUT directory
        is reached by `_read_small` and by nothing else: one `openat` over `objects/<ab>/<rest>`
        applies `O_NOFOLLOW` only to `<rest>`, so the commit is read from OUTSIDE the checkout and
        the verdict describes a repository the caller never named."""
        target = self.committed("linked-fanout", "AGENTS.md", ".gitlab-ci.yml")
        git = target / ".git"
        oid = (git / "refs" / "heads" / "main").read_text(encoding="utf-8").strip()
        fanout = git / "objects" / oid[:2]
        outside = self.tmp_root / "outside-fanout"
        fanout.rename(outside)
        fanout.symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"commit {oid} is not readable: {oid[:2]} is a symlink")
        self.assertEqual(result["occupied"], [], result)
        # The refusal has to be the CONTAINMENT guard and not an errno from a fixture pointing at
        # nothing: an ENOENT refusal would pass this test while proving nothing whatsoever.
        self.assertFalse(
            any(errno.errorcode[errno.ENOENT] in item["detail"] for item in result["ambiguities"]),
            f"the refusal must name the symlink, not an absence: {result['ambiguities']}",
        )
        # Positive control: the identical bytes moved back INSIDE the checkout resolve through the
        # very same object path and name both committed surfaces, so the refusal above is
        # attributable to the symlinked fanout rather than to a decoy that was never readable.
        fanout.unlink()
        outside.rename(fanout)
        control = self.assertVerdict(target, "brownfield")
        self.assertOccupied(control, "guidance", "HEAD:AGENTS.md")
        self.assertOccupied(control, "ci", "HEAD:.gitlab-ci.yml")

    def test_a_symref_chain_in_the_branch_is_refuse_and_ask(self) -> None:
        target = self.repo("symref", commit=True, readme=True)
        branch = target / ".git" / "refs" / "heads" / "main"
        oid = branch.read_text(encoding="utf-8").strip()
        branch.write_text("ref: refs/heads/other\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "not a direct object id")
        branch.write_text(f"{oid}\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_an_oversized_object_is_refused_rather_than_inflated(self) -> None:
        target = self.repo("bomb", readme=True)
        git = target / ".git"
        oid = "b" * 40
        payload = b"commit 200000\0" + b"x" * 200000
        directory = git / "objects" / oid[:2]
        directory.mkdir(parents=True)
        (directory / oid[2:]).write_bytes(zlib.compress(payload))
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", errno.errorcode[errno.EFBIG])
        # Positive control: a real commit at the same path is greenfield, so the refusal is
        # the inflation bound rather than the object path or the ref.
        (directory / oid[2:]).unlink()
        (git / "refs" / "heads" / "main").write_text(f"{write_commit(git)}\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_non_commit_object_at_head_is_refuse_and_ask(self) -> None:
        target = self.repo("blobhead", readme=True)
        git = target / ".git"
        payload = b"blob 2\0hi"
        oid = hashlib.sha1(payload, usedforsecurity=False).hexdigest()
        directory = git / "objects" / oid[:2]
        directory.mkdir(parents=True)
        (directory / oid[2:]).write_bytes(zlib.compress(payload))
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "is not a commit object")

    def test_named_evidence_is_bounded_and_says_how_much_it_omitted(self) -> None:
        target = self.repo("many", commit=True, readme=True)
        for index in range(rc.MAX_NAMED_ENTRIES + 5):
            (target / f"entry{index:03d}").write_text("x\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "(+5 more)")
        self.assertAmbiguity(result, "unclassified-content", f"{rc.MAX_NAMED_ENTRIES + 5} entries")
        detail = next(item["detail"] for item in result["ambiguities"] if item["kind"] == "unclassified-content")
        self.assertIn(f"entry{rc.MAX_NAMED_ENTRIES - 1:03d}", detail)
        self.assertNotIn(f"entry{rc.MAX_NAMED_ENTRIES:03d}", detail)

    def test_an_unreadable_parent_is_an_ambiguity_and_not_an_absence(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions, so the probe cannot fail")
        target = self.repo("unreadable", commit=True, readme=True)
        docs = target / "docs"
        (docs / "adr").mkdir(parents=True)
        docs.chmod(0o000)
        self.addCleanup(docs.chmod, 0o755)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "undetermined-surface", "docs/adr")
        # Positive control: readable, the same `docs/adr` is a named occupied decision
        # surface, so the ambiguity is the permission failure and not a missing path.
        docs.chmod(0o755)
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "decision", "docs/adr")

    def test_a_component_whose_own_stat_also_fails_is_undetermined(self) -> None:
        """The component classifier's LAST arm, which the unreadable-parent test above does not
        reach: there the failed component still stat-ed successfully, so the directory check
        answered. A directory that is readable but not SEARCHABLE fails both the open AND the
        stat of everything under it, and answering that with absence is the same
        redirect-or-hide-earns-greenfield conclusion one link out."""
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions, so the probe cannot fail")
        target = self.repo("unsearchable", commit=True)
        (target / ".config" / "mise").mkdir(parents=True)
        (target / ".config" / "mise" / "config.toml").write_text("[tools]\n", encoding="utf-8")
        (target / ".config").chmod(0o400)  # readable, so it OPENS; not searchable, so `mise` cannot be stat-ed.
        self.addCleanup((target / ".config").chmod, 0o755)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "undetermined-surface", f".config/mise/config.toml: mise: {errno.errorcode[errno.EACCES]}")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: searchable, the very same path is a named occupied toolchain surface,
        # so the ambiguity is the permission failure and not a candidate that was never there.
        (target / ".config").chmod(0o755)
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "toolchain", ".config/mise/config.toml")

    def test_a_symlinked_allowlisted_working_entry_does_not_pass(self) -> None:
        """`README.md` is an allowlisted NAME. As a symlink it can point anywhere -- including out
        of the checkout -- and the allowlist deliberately never follows it, so the only safe
        answer is to name it."""
        target = self.repo("linked-readme", commit=True)
        outside = self.tmp_root / "outside-readme.md"
        outside.write_text("# foreign intent\n", encoding="utf-8")
        (target / "README.md").symlink_to(outside)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "README.md")
        # Positive control: the same allowlisted name as a REGULAR file is greenfield, so the
        # ambiguity is the node type rather than the name leaving the allowlist.
        (target / "README.md").unlink()
        (target / "README.md").write_text("# intent\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_an_allowlisted_entry_that_cannot_be_stat_ed_is_not_waved_through(self) -> None:
        """The race this arm exists for: a name that is LISTED and then becomes unreachable before
        it is stat-ed. Patched because no on-disk shape reaches it -- a dangling symlink still
        lstats, and an unsearchable target directory is refused earlier at `.git` -- and waving an
        unknown node through a permitted NAME is what would let hidden content earn greenfield."""
        target = self.repo("unstatable-readme", commit=True, readme=True)
        real_stat = os.stat

        def stat_that_fails_for_the_readme(path, *args, **kwargs):
            if path == "README.md":
                raise PermissionError(errno.EACCES, "the entry became unreachable after it was listed")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(rc.os, "stat", stat_that_fails_for_the_readme):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "README.md")
        # Positive control: unpatched, the identical repository passes the same allowlist and is
        # greenfield, so the ambiguity is the failed stat and not the README itself.
        self.assertVerdict(target, "greenfield")

    def test_an_unreadable_root_listing_is_an_ambiguity_and_not_an_empty_worktree(self) -> None:
        """Patched for the same reason: the root descriptor is opened for reading before anything
        is listed, so a real EACCES here needs a race. Reading `no entries` off a failed listing
        would erase every unclassified file at once."""
        target = self.repo("unlistable-root", commit=True, readme=True)
        (target / "src").mkdir()
        real_listdir = os.listdir
        root_inode = target.stat().st_ino

        def listdir_that_fails_on_the_worktree_root(fd):
            if isinstance(fd, int) and os.fstat(fd).st_ino == root_inode:
                raise PermissionError(errno.EACCES, "the worktree root became unreadable")
            return real_listdir(fd)

        with mock.patch.object(rc.os, "listdir", listdir_that_fails_on_the_worktree_root):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "undetermined-surface", f".: {errno.errorcode[errno.EACCES]}")
        # Positive control: unpatched, the same root lists `src` and names it as content, so the
        # refusal above is the failed listing rather than a channel that never reports anything.
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "unclassified-content", "src")

    def test_a_symlinked_hooks_directory_is_not_read_through(self) -> None:
        target = self.repo("linked-hooks", commit=True, readme=True)
        git = target / ".git"
        outside = self.tmp_root / "outside-hooks"
        outside.mkdir()
        (outside / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        for sample in sorted((git / "hooks").iterdir()):
            sample.unlink()
        (git / "hooks").rmdir()
        (git / "hooks").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "undetermined-surface", ".git/hooks: hooks is a symlink")
        self.assertEqual(result["occupied"], [], result)
        # The decoy is a REAL installed hook: moving the same directory inside `.git` makes it a
        # named occupied hook surface, so the ambiguity is the custody guard rather than an absent
        # or empty hooks directory.
        (git / "hooks").unlink()
        outside.rename(git / "hooks")
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "hook", ".git/hooks/pre-commit")

    def test_an_unterminated_object_stream_is_refused_rather_than_trusted(self) -> None:
        """The end-of-stream half of the inflation guard, which the oversized object above cannot
        reach: a stream that never ends inflates COMPLETELY and leaves no unconsumed tail, so only
        that half can see it. A commit's `parent` headers sit after its `tree` header, so a stream
        that stops early reads as a parentless commit -- an emptier history than the object holds.
        """
        target = self.repo("unterminated", readme=True)
        git = target / ".git"
        body = b"tree " + EMPTY_TREE.encode() + b"\nauthor A <a@example.invalid> 0 +0000\ncommitter A <a@example.invalid> 0 +0000\n\nc\n"
        oid = write_unterminated_object(git, b"commit", body)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"commit {oid} is not readable: {errno.errorcode[errno.EFBIG]}")
        # Positive control: the SAME payload at the SAME object id and path, under a terminated
        # stream, is greenfield -- so the refusal is the missing end of the stream and nothing else.
        self.assertEqual(write_object(git, b"commit", body), oid)
        self.assertVerdict(target, "greenfield")

    def test_a_corrupt_object_stream_names_the_zlib_failure(self) -> None:
        """`zlib.error` is a READ_FAILURE on purpose: a stream that will not inflate is an
        ambiguity to report, not an exception that loses the JSON result."""
        target = self.repo("corrupt-object", readme=True)
        git = target / ".git"
        oid = "d" * 40
        directory = git / "objects" / oid[:2]
        directory.mkdir(parents=True)
        (directory / oid[2:]).write_bytes(b"not a zlib stream at all")
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "malformed zlib stream")
        # Positive control: a real inflatable commit through the same reader is greenfield, so the
        # refusal is the corrupt stream and not the object path or the ref.
        (directory / oid[2:]).unlink()
        (git / "refs" / "heads" / "main").write_text(f"{write_commit(git)}\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")


class CommittedTreeTests(ClassifierTestCase):
    """The COMMITTED tree is a second occupancy surface, and reading only the working tree was
    the live defect: commit `AGENTS.md`, `.gitlab-ci.yml`, and `.github/workflows/ci.yml`, remove
    them from the checkout, and the repository was reported greenfield with zero ambiguities --
    the GitLab misclassification and full-baseline harm ADR-0022 lines 20-21 reject by name.

    Every test here builds the surface in HEAD ONLY, with an empty working tree, so a fix that
    merely re-checks the checkout cannot pass any of them."""

    def assertCommittedSurface(self, name: str, in_tree: str, candidate: str, surface: str, *, mode: int = BLOB_MODE) -> None:
        target = self.committed(name, in_tree, mode=mode)

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, surface, f"HEAD:{candidate}")
        self.assertEqual(sorted(os.listdir(target)), [".git"], "the surface must exist ONLY in HEAD")
        # Positive control: the same builder committing one allowlisted README is greenfield, so
        # the brownfield verdict is the committed surface and not the mere fact of a commit --
        # and it proves the walk reads a REAL tree rather than short-circuiting on the empty one.
        self.assertVerdict(self.committed(f"{name}-control", "README.md"), "greenfield")

    def test_the_reproduced_gitlab_repository_is_not_greenfield(self) -> None:
        target = self.committed("gitlab-committed", "AGENTS.md", ".gitlab-ci.yml", ".github/workflows/ci.yml")

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, "guidance", "HEAD:AGENTS.md")
        self.assertOccupied(result, "ci", "HEAD:.gitlab-ci.yml")
        self.assertOccupied(result, "ci", "HEAD:.github/workflows")
        self.assertEqual(sorted(os.listdir(target)), [".git"], "the working tree is bare on purpose")
        self.assertVerdict(self.committed("gitlab-committed-control", "README.md"), "greenfield")

    def test_a_committed_jenkinsfile_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("jenkins-committed", "Jenkinsfile", "Jenkinsfile", "ci")

    def test_a_committed_buildkite_directory_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("buildkite-committed", ".buildkite/pipeline.yml", ".buildkite", "ci")

    def test_a_committed_agents_md_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("agents-committed", "AGENTS.md", "AGENTS.md", "guidance")

    def test_a_committed_seeds_queue_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("seeds-committed", ".seeds/queue.jsonl", ".seeds", "queue")

    def test_a_committed_docs_adr_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("adr-committed", "docs/adr/0001-x.md", "docs/adr", "decision")

    def test_a_committed_mise_toml_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("mise-committed", "mise.toml", "mise.toml", "toolchain")

    def test_a_committed_activation_contract_is_not_greenfield(self) -> None:
        self.assertCommittedSurface("contract-committed", ".agentic-sdlc/repo.toml", ".agentic-sdlc", "contract")

    def test_the_deepest_candidate_is_reached_by_the_prefix_directed_descent(self) -> None:
        """`.config/mise/config.toml` needs two levels of descent, so it proves the walk follows
        candidate prefixes rather than only reading the root tree."""
        self.assertCommittedSurface("deep-committed", ".config/mise/config.toml", ".config/mise/config.toml", "toolchain")

    def test_a_committed_symlinked_surface_still_occupies_it(self) -> None:
        self.assertCommittedSurface("symlink-committed", "AGENTS.md", "AGENTS.md", "guidance", mode=SYMLINK_MODE)

    def test_a_committed_surface_outranks_the_parent_history_ambiguity(self) -> None:
        target = self.repo("history-and-surface")
        git = target / ".git"
        first = write_commit(git)
        tree = build_tree(git, {"Jenkinsfile": (BLOB_MODE, write_blob(git))})
        self.commit_tree(target, tree, parents=(first,))

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, "ci", "HEAD:Jenkinsfile")
        self.assertAmbiguity(result, "commit-history", "parent")
        # Positive control: the identical two-commit history with an EMPTY tree is only
        # refuse-and-ask, so the brownfield verdict is the committed surface outranking the
        # parent ambiguity rather than anything about the history.
        self.commit_tree(target, EMPTY_TREE, parents=(first,))
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "commit-history", "parent")

    def test_a_working_tree_surface_short_circuits_before_the_committed_walk(self) -> None:
        """Documented, not accidental: one occupied surface is brownfield outright, so the
        committed walk -- which only ever serves greenfield -- is not run. The VERDICT is the
        same either way; only the evidence list is shorter."""
        target = self.committed("shortcircuit", "AGENTS.md")
        (target / ".gitlab-ci.yml").write_text("stages: [test]\n", encoding="utf-8")

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, "ci", ".gitlab-ci.yml")
        self.assertFalse(any(item["path"].startswith("HEAD:") for item in result["occupied"]), result["occupied"])
        # Positive control: removing the working-tree file makes the committed surface appear, so
        # the absence above is the short circuit and not a walk that can never see anything.
        (target / ".gitlab-ci.yml").unlink()
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "guidance", "HEAD:AGENTS.md")

    def test_committed_content_outside_the_allowlist_is_refuse_and_ask(self) -> None:
        target = self.committed("committed-content", "src/main.c", "notes.txt")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "src")
        self.assertAmbiguity(result, "commit-tree", "notes.txt")
        self.assertAmbiguity(result, "commit-tree", "2 entries outside the allowlist")
        self.assertVerdict(self.committed("committed-content-control", "README.md"), "greenfield")

    def test_a_committed_allowlisted_name_that_is_a_directory_does_not_pass(self) -> None:
        """`LICENSE` is an allowlisted NAME. A tree wearing it would hide an occupied surface
        beneath a permitted name, and the walk deliberately never descends into an allowlisted
        entry, so the ONLY safe answer is to name it."""
        target = self.committed("license-directory", "LICENSE/.gitlab-ci.yml")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "LICENSE")
        # Positive control: the same name as a regular blob IS allowlisted and greenfield, so the
        # ambiguity is the entry's mode rather than the name.
        self.assertVerdict(self.committed("license-file", "LICENSE"), "greenfield")

    def test_a_committed_allowlisted_name_that_is_a_symlink_does_not_pass(self) -> None:
        target = self.committed("readme-symlink", "README.md", mode=SYMLINK_MODE)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "README.md")
        self.assertVerdict(self.committed("readme-blob", "README.md"), "greenfield")

    def test_a_committed_entry_named_git_does_not_pass_the_allowlist(self) -> None:
        """`.git` is allowlisted in the WORKING tree because every repository has one; a tree can
        never legitimately carry that name, so a committed one is named rather than waved past."""
        target = self.committed("committed-dotgit", ".git")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", ".git")
        self.assertVerdict(self.committed("committed-dotgit-control", "README.md"), "greenfield")

    def test_a_working_tree_allowlisted_name_that_is_a_directory_does_not_pass(self) -> None:
        target = self.repo("wt-license-directory", commit=True)
        (target / "LICENSE").mkdir()
        (target / "LICENSE" / ".gitlab-ci.yml").write_text("x\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "unclassified-content", "LICENSE")
        # Positive control: the same allowlisted name as a regular file is greenfield, so the
        # ambiguity is the node type and not the name leaving the allowlist entirely.
        (target / "LICENSE" / ".gitlab-ci.yml").unlink()
        (target / "LICENSE").rmdir()
        (target / "LICENSE").write_text("MIT\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_packed_tree_is_refuse_and_ask(self) -> None:
        target = self.repo("packed-tree")
        git = target / ".git"
        blob = write_blob(git)
        tree = build_tree(git, {"AGENTS.md": (BLOB_MODE, blob)})
        object_path(git, tree).unlink()  # As far as this module can see, the tree is packed.
        self.commit_tree(target, tree)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", f"tree {tree} is not a loose object")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: restoring the byte-identical loose tree makes the SAME repository
        # brownfield on the committed AGENTS.md, so the refusal is the unreadable tree and not a
        # tree that never carried a surface.
        self.assertEqual(build_tree(git, {"AGENTS.md": (BLOB_MODE, blob)}), tree)
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "guidance", "HEAD:AGENTS.md")

    def test_an_unparsable_tree_names_the_malformation(self) -> None:
        target = self.repo("unparsable-tree")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"100644 no-nul-and-no-oid"))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "is unparsable: a tree entry has no name")
        # Positive control: a well-formed tree at the same position parses and is greenfield, so
        # the refusal is the malformation rather than every hand-built tree.
        self.commit_tree(target, build_tree(git, {"README.md": (BLOB_MODE, write_blob(git))}))
        self.assertVerdict(target, "greenfield")

    def test_a_truncated_tree_entry_names_the_malformation(self) -> None:
        target = self.repo("truncated-tree")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"100644 short\0" + bytes.fromhex("0" * 20)))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "a tree entry is truncated")

    def test_a_tree_whose_header_size_disagrees_with_its_payload_is_refuse_and_ask(self) -> None:
        """A corrupt or crafted object whose declared size does not match what it carries is not
        a tree this module can trust to be complete, so its entry list is not evidence."""
        target = self.repo("lying-header")
        git = target / ".git"
        body = b"100644 README.md\0" + bytes.fromhex("0" * 40)
        self.commit_tree(target, write_raw_object(git, b"tree 5\0" + body))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "object header disagrees with its payload")
        # Positive control: the very same body under a truthful header parses to one allowlisted
        # README and is greenfield, so the refusal is the size disagreement and nothing else.
        self.commit_tree(target, write_object(git, b"tree", body))
        self.assertVerdict(target, "greenfield")

    def test_a_blob_where_the_commit_named_a_tree_is_refuse_and_ask(self) -> None:
        target = self.repo("blob-as-root-tree")
        git = target / ".git"
        self.commit_tree(target, write_blob(git, b"not a tree\n"))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "is a blob, not the tree its parent named")
        self.assertVerdict(self.committed("blob-as-root-tree-control", "README.md"), "greenfield")

    def test_a_blob_where_a_subtree_was_named_is_refuse_and_ask(self) -> None:
        """The same type check one level down: `.github` claims mode 040000 while its object is a
        blob, so every candidate beneath it is UNKNOWN rather than absent."""
        target = self.repo("blob-as-subtree")
        git = target / ".git"
        self.commit_tree(target, write_tree(git, {".github": (TREE_MODE, write_blob(git, b"not a tree\n"))}))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "HEAD:.github")
        self.assertAmbiguity(result, "commit-tree", "is a blob, not the tree its parent named")
        # Positive control: a real `.github` tree is reached by the same descent and reports the
        # occupied CI surface, so the ambiguity is the type check and not a failure to descend.
        control = self.committed("blob-as-subtree-control", ".github/workflows/ci.yml")
        self.assertOccupied(self.assertVerdict(control, "brownfield"), "ci", "HEAD:.github/workflows")

    def test_a_committed_submodule_at_a_candidate_prefix_is_refuse_and_ask(self) -> None:
        target = self.repo("submodule-prefix")
        git = target / ".git"
        self.commit_tree(target, write_tree(git, {"docs": (GITLINK_MODE, "0" * 40)}))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "HEAD:docs is a submodule")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: the same `docs` name as a real tree carrying `adr` is a named occupied
        # decision surface, so the refusal is the gitlink and not the path.
        control = self.committed("submodule-prefix-control", "docs/adr/0001-x.md")
        self.assertOccupied(self.assertVerdict(control, "brownfield"), "decision", "HEAD:docs/adr")

    def test_a_committed_submodule_at_a_candidate_path_is_the_occupied_surface(self) -> None:
        target = self.repo("submodule-queue")
        git = target / ".git"
        self.commit_tree(target, write_tree(git, {".seeds": (GITLINK_MODE, "0" * 40)}))

        result = self.assertVerdict(target, "brownfield")

        self.assertOccupied(result, "queue", "HEAD:.seeds")
        self.assertTrue(any(item["kind"] == "submodule" for item in result["occupied"]), result["occupied"])

    def test_a_non_utf8_tree_entry_name_is_refuse_and_ask(self) -> None:
        target = self.repo("non-utf8-name")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"100644 caf\xe9.md\0" + bytes.fromhex("0" * 40)))

        first = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(first, "commit-tree", "not UTF-8")
        # Positive control: the same tree with a decodable name PARSES -- it lands in the
        # allowlist ambiguity instead -- so the refusal above is the decode and not the shape.
        self.commit_tree(target, write_object(git, b"tree", b"100644 cafe.md\0" + bytes.fromhex("0" * 40)))
        second = self.assertVerdict(target, "refuse-and-ask")
        self.assertAmbiguity(second, "commit-tree", "cafe.md")
        self.assertFalse(any("not UTF-8" in item["detail"] for item in second["ambiguities"]), second)

    def test_an_oversized_tree_is_refused_rather_than_inflated(self) -> None:
        target = self.repo("tree-bomb")
        git = target / ".git"
        body = b"".join(f"100644 entry{index:05d}".encode() + b"\0" + bytes.fromhex("0" * 40) for index in range(4000))
        self.assertGreater(len(body), rc.MAX_OBJECT_BYTES)
        self.commit_tree(target, write_object(git, b"tree", body))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", errno.errorcode[errno.EFBIG])
        # Positive control: a small well-formed tree at the same position is greenfield.
        self.commit_tree(target, build_tree(git, {"README.md": (BLOB_MODE, write_blob(git))}))
        self.assertVerdict(target, "greenfield")

    def test_a_commit_without_a_tree_header_is_refuse_and_ask(self) -> None:
        target = self.repo("treeless-commit")
        git = target / ".git"
        body = b"author A <a@example.invalid> 0 +0000\ncommitter A <a@example.invalid> 0 +0000\n\nc\n"
        oid = write_object(git, b"commit", body)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "does not name a tree")
        # Positive control: the identical repository with a well-formed commit is greenfield.
        self.commit_tree(target, EMPTY_TREE)
        self.assertVerdict(target, "greenfield")

    def test_an_object_with_no_type_header_is_not_an_empty_tree(self) -> None:
        """`tree 0` with no NUL separator has no payload at all, and reading it as a well-formed
        empty tree is a false-empty with nothing behind it: the header/payload split is what makes
        `an empty tree` and `an object this module cannot parse` different answers."""
        target = self.repo("headerless-tree")
        git = target / ".git"
        self.commit_tree(target, write_raw_object(git, b"tree 0"))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "object has no type header")
        # Positive control: a well-formed tree carrying one surface, reached through the same
        # reader, is named -- so the refusal is the missing separator and not the walk.
        self.commit_tree(target, build_tree(git, {"AGENTS.md": (BLOB_MODE, write_blob(git))}))
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "guidance", "HEAD:AGENTS.md")

    def test_an_object_whose_declared_size_is_not_a_number_is_refuse_and_ask(self) -> None:
        """The numeric check is not redundant with the size comparison it precedes: without it the
        comparison raises `ValueError`, which is NOT a read failure, so the whole classification
        would be lost instead of reporting one unparsable object."""
        target = self.repo("nonnumeric-size")
        git = target / ".git"
        body = b"100644 README.md\0" + bytes.fromhex("0" * 40)
        self.commit_tree(target, write_raw_object(git, b"tree x\0" + body))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "object header disagrees with its payload")
        # Positive control: the identical body under a truthful numeric header parses to one
        # allowlisted README and is greenfield.
        self.commit_tree(target, write_object(git, b"tree", body))
        self.assertVerdict(target, "greenfield")

    def test_a_tree_entry_with_no_mode_names_the_malformation(self) -> None:
        """An entry that begins at its separator has an EMPTY mode. Without the check the empty
        mode passes the octal test and `int(b"", 8)` raises `ValueError`, which is not a read
        failure, so the result would be lost rather than named."""
        target = self.repo("modeless-entry")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b" README.md\0" + bytes.fromhex("0" * 40)))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "a tree entry has no mode")
        # Positive control: the same name with a real mode parses and is greenfield.
        self.commit_tree(target, write_object(git, b"tree", b"100644 README.md\0" + bytes.fromhex("0" * 40)))
        self.assertVerdict(target, "greenfield")

    def test_an_overlong_tree_entry_mode_names_the_malformation(self) -> None:
        """`0100644` is seven octal digits: it is not a mode Git writes, and accepting it would let
        a crafted entry wear a mode this walk interprets. The length half of the check is the only
        thing that sees it, because every character IS an octal digit."""
        target = self.repo("overlong-mode")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"0100644 AGENTS.md\0" + bytes.fromhex("0" * 40)))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "a tree entry mode is not octal")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: the same entry at six digits IS interpreted and names the occupied
        # guidance surface, so the refusal is the mode's length rather than the entry.
        self.commit_tree(target, write_object(git, b"tree", b"100644 AGENTS.md\0" + bytes.fromhex("0" * 40)))
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "guidance", "HEAD:AGENTS.md")

    def test_a_non_octal_tree_entry_mode_names_the_malformation(self) -> None:
        target = self.repo("non-octal-mode")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"100648 AGENTS.md\0" + bytes.fromhex("0" * 40)))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "a tree entry mode is not octal")
        # Positive control: the same six-character mode with only octal digits is interpreted.
        self.commit_tree(target, write_object(git, b"tree", b"100644 AGENTS.md\0" + bytes.fromhex("0" * 40)))
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "guidance", "HEAD:AGENTS.md")

    def test_a_tree_entry_name_holding_a_separator_names_the_malformation(self) -> None:
        """Git writes one path component per entry. A name carrying `/` would let a crafted tree
        assert a path its own structure does not have -- here a `docs/adr` that no `docs` tree
        contains -- so the entry list is not evidence about any path at all."""
        target = self.repo("slashed-entry")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"40000 docs/adr\0" + bytes.fromhex("0" * 40)))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "a tree entry name is not one path component")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: the real two-level shape -- a `docs` tree holding `adr` -- IS named as
        # the occupied decision surface, so the refusal is the crafted name and not the path.
        control = self.committed("slashed-entry-control", "docs/adr/0001-x.md")
        self.assertOccupied(self.assertVerdict(control, "brownfield"), "decision", "HEAD:docs/adr")

    def test_a_dot_tree_entry_name_names_the_malformation(self) -> None:
        target = self.repo("dot-entry")
        git = target / ".git"
        self.commit_tree(target, write_object(git, b"tree", b"40000 ..\0" + bytes.fromhex("0" * 40)))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "a tree entry name is not one path component")
        # The refusal must be the PARSE and not the allowlist downstream of it: a `..` that reached
        # the root list would be reported as ordinary unallowlisted content instead.
        self.assertFalse(
            any("outside the allowlist" in item["detail"] for item in result["ambiguities"]),
            f"a dot entry is an unparsable tree, not an allowlist question: {result['ambiguities']}",
        )
        # Positive control: an ordinary name in the same position parses, and the allowlist channel
        # then really does report it -- so neither assertion above is passing on silence.
        self.commit_tree(target, write_object(git, b"tree", b"40000 notes\0" + bytes.fromhex("0" * 40)))
        second = self.assertVerdict(target, "refuse-and-ask")
        self.assertAmbiguity(second, "commit-tree", "outside the allowlist: notes")
        self.assertFalse(any("not one path component" in item["detail"] for item in second["ambiguities"]), second)

    def test_a_first_header_that_only_looks_like_a_tree_line_is_refuse_and_ask(self) -> None:
        """`tree ` is an exact five-byte prefix, and slicing past it without checking would read
        the tail of ANY 45-character first header as the tree id -- here `treex<id>`, which names
        the empty tree and would earn greenfield off a commit that declares no tree at all."""
        target = self.repo("pseudo-tree-header")
        git = target / ".git"
        body = b"treex" + EMPTY_TREE.encode() + b"\nauthor A <a@example.invalid> 0 +0000\n\nc\n"
        oid = write_object(git, b"commit", body)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "does not name a tree in its first header")
        # Positive control: the same id behind a real `tree ` header is greenfield, so the refusal
        # is the missing separator in the header and not the tree id.
        self.commit_tree(target, EMPTY_TREE)
        self.assertVerdict(target, "greenfield")

    def test_a_tree_value_that_is_not_an_object_id_is_named_as_a_history_ambiguity(self) -> None:
        """Git writes lowercase hex. An uppercase value is not the id this module could look up, so
        it is refused where it is READ -- naming the commit -- rather than carried one link further
        and reported as a missing tree object, which would blame the wrong file."""
        target = self.repo("uppercase-tree-value")
        git = target / ".git"
        body = b"tree " + EMPTY_TREE.upper().encode() + b"\nauthor A <a@example.invalid> 0 +0000\n\nc\n"
        oid = write_object(git, b"commit", body)
        (git / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "does not name a tree in its first header")
        self.assertFalse(
            any(item["kind"] == "commit-tree" for item in result["ambiguities"]),
            f"the value never becomes a tree to look up: {result['ambiguities']}",
        )
        # Positive control: the lowercase spelling of the same id is greenfield.
        self.commit_tree(target, EMPTY_TREE)
        self.assertVerdict(target, "greenfield")

    def test_the_well_known_empty_tree_id_is_proof_without_a_read(self) -> None:
        target = self.repo("empty-tree", commit=True, readme=True)

        self.assertIn(EMPTY_TREE, rc.EMPTY_TREE_OIDS)
        self.assertFalse(object_path(target / ".git", EMPTY_TREE).exists(), "the empty tree is NOT on disk")
        self.assertVerdict(target, "greenfield")
        # Positive control: any OTHER absent tree id refuses, so the greenfield above comes from
        # recognizing the empty-tree hash and not from tolerating a missing tree object.
        missing = "c" * 40
        self.commit_tree(target, missing)
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "commit-tree", f"tree {missing} is not a loose object")


class CommittedWalkBoundTests(ClassifierTestCase):
    """The committed walk is bounded, and EXCEEDING A BOUND IS A REFUSAL, never an absence.

    Both bounds are headroom over figures derived from the shipped candidate table, so no
    shipped table can reach them -- which is the point. The distinguishing input is therefore a
    patched `CANDIDATE_PREFIXES`: it is the only thing that decides how far the walk descends,
    and patching it is what lets these tests drive the guards at all."""

    def test_each_empty_tree_id_is_the_hash_of_an_empty_tree(self) -> None:
        """The shortcut skips a read for these ids, so its whole justification is that each one
        IS the hash of the empty tree's serialization. A wrong constant would let a real tree at
        that id go unread, so this derives them instead of trusting the literals -- and both
        match what `git hash-object -t tree /dev/null` reports in each object format."""
        serialized = b"tree 0\0"
        derived = {hashlib.sha1(serialized, usedforsecurity=False).hexdigest(), hashlib.sha256(serialized).hexdigest()}

        self.assertEqual(rc.EMPTY_TREE_OIDS, derived)
        self.assertEqual(hashlib.sha1(serialized, usedforsecurity=False).hexdigest(), EMPTY_TREE)
        # Negative control on the same channel: a near-miss id is NOT in the set, so the equality
        # above is a real comparison and not a set that admits anything.
        self.assertNotIn(EMPTY_TREE[:-1] + "5", rc.EMPTY_TREE_OIDS)

    def test_the_bounds_are_headroom_over_the_shipped_candidate_table(self) -> None:
        deepest = max(len(relative.split("/")) for _, relative in rc.CANDIDATES)

        self.assertLessEqual(len(rc.CANDIDATE_PREFIXES) + 1, rc.MAX_TREE_OBJECTS)
        self.assertLessEqual(deepest, rc.MAX_TREE_DEPTH)
        # The prefix set must be DERIVED from the table, or the walk never descends at all.
        self.assertIn(".github", rc.CANDIDATE_PREFIXES)
        self.assertIn(".config/mise", rc.CANDIDATE_PREFIXES)
        self.assertNotIn("AGENTS.md", rc.CANDIDATE_PREFIXES)

    def chain(self, name: str, depth: int) -> Path:
        """A repository whose committed tree is one `level0/level1/.../leaf.txt` chain."""
        target = self.tmp_root / name
        target.mkdir()
        git = make_git(target)
        path = "/".join(f"level{index}" for index in range(depth)) + "/leaf.txt"
        self.commit_tree(target, build_tree(git, {path: (BLOB_MODE, write_blob(git))}))
        return target

    def wide(self, name: str, count: int) -> tuple[Path, frozenset[str]]:
        """A repository whose committed root tree holds `count` distinct sibling subtrees."""
        target = self.tmp_root / name
        target.mkdir()
        git = make_git(target)
        blob = write_blob(git)
        branches = [f"branch{index:02d}" for index in range(count)]
        # Each subtree carries a DISTINCT leaf name, so every one is a distinct object the walk
        # must actually read -- identical subtrees would share one object id and one read.
        self.commit_tree(target, build_tree(git, {f"{branch}/leaf-{branch}.txt": (BLOB_MODE, blob) for branch in branches}))
        return target, frozenset(branches)

    def test_exceeding_the_depth_bound_refuses_rather_than_recursing(self) -> None:
        prefixes = frozenset(
            "/".join(f"level{index}" for index in range(count + 1)) for count in range(rc.MAX_TREE_DEPTH + 4)
        )
        deep = self.chain("deep-chain", rc.MAX_TREE_DEPTH + 3)
        shallow = self.chain("shallow-chain", rc.MAX_TREE_DEPTH - 1)

        with mock.patch.object(rc, "CANDIDATE_PREFIXES", prefixes):
            deep_result = self.assertVerdict(deep, "refuse-and-ask")
            shallow_result = self.assertVerdict(shallow, "refuse-and-ask")

        self.assertAmbiguity(deep_result, "commit-tree", f"{rc.MAX_TREE_DEPTH}-level depth bound")
        # Positive control: the SAME patched prefix set on a chain inside the bound produces no
        # depth ambiguity, so the refusal is the bound and not the patch or the chain shape.
        self.assertFalse(any("depth bound" in item["detail"] for item in shallow_result["ambiguities"]), shallow_result)

    def test_exceeding_the_object_bound_refuses_rather_than_reading_more(self) -> None:
        many, many_prefixes = self.wide("wide-over", rc.MAX_TREE_OBJECTS + 4)
        few, few_prefixes = self.wide("wide-under", rc.MAX_TREE_OBJECTS - 4)

        with mock.patch.object(rc, "CANDIDATE_PREFIXES", many_prefixes):
            over = self.assertVerdict(many, "refuse-and-ask")
        with mock.patch.object(rc, "CANDIDATE_PREFIXES", few_prefixes):
            under = self.assertVerdict(few, "refuse-and-ask")

        self.assertAmbiguity(over, "commit-tree", f"{rc.MAX_TREE_OBJECTS}-object bound")
        # Positive control: the same builder under the bound reports no object-bound ambiguity,
        # so the refusal is the ceiling rather than the patched prefix set itself.
        self.assertFalse(any("object bound" in item["detail"] for item in under["ambiguities"]), under)
        # The bound STOPS the walk: it names the one place it stopped, rather than draining the
        # queue and reporting every subtree it had already decided not to read, which a reader
        # cannot tell apart from real findings.
        self.assertEqual(len([item for item in over["ambiguities"] if "object bound" in item["detail"]]), 1, over)


class RefResolutionTests(ClassifierTestCase):
    """The chain from HEAD to a tree, one link at a time, with the SAME rule at each link: a
    surface that is present but unreadable or malformed must never be answered as absence.

    The reproduction shape is always the same and it is deliberately the expensive one -- a
    repository whose HEAD tree carries `AGENTS.md` and `.gitlab-ci.yml` -- because a false
    greenfield here is what authorizes writing a baseline over it. Every test's positive control
    resolves the SAME repository through the SAME channel and reports those two surfaces, so a
    refusal can never come from a fixture that had nothing in it.
    """

    def occupied_repository(self, name: str) -> Path:
        """A repository with real committed history: `AGENTS.md` and `.gitlab-ci.yml` in HEAD."""
        return self.committed(name, "AGENTS.md", ".gitlab-ci.yml")

    def assertSeesTheCommittedSurfaces(self, target: Path) -> None:
        """The positive control every test in this class shares."""
        result = self.assertVerdict(target, "brownfield")
        self.assertOccupied(result, "guidance", "HEAD:AGENTS.md")
        self.assertOccupied(result, "ci", "HEAD:.gitlab-ci.yml")

    def assertPackedValueIsRefused(self, name: str, value: str, fragment: str) -> None:
        target = self.occupied_repository(name)
        oid = self.unpack_branch(target)
        self.write_packed_refs(target, f"{value} refs/heads/main")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", fragment)
        # The surfaces are INVISIBLE while the ref is unresolved, which is exactly why treating
        # the malformed value as an unborn branch reported greenfield with nothing in the list.
        self.assertEqual(result["occupied"], [], result)
        # Positive control: the real object id through the identical packed-refs channel resolves
        # to the same commit and names both surfaces, so the refusal is the malformed VALUE.
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_truncated_packed_object_id_is_refuse_and_ask(self) -> None:
        """The reported defect. A 39-character value fails `_is_object_id`, fell out of the
        lookup as None, and was read one frame up as an unborn branch."""
        target = self.occupied_repository("packed-truncated-probe")
        oid = self.unpack_branch(target)
        self.assertFalse(rc._is_object_id(oid[:-1]), "the truncated value must really fail the check")

        self.assertPackedValueIsRefused("packed-truncated", oid[:-1], "is packed at a value that is not an object id")
        del target

    def test_a_packed_object_id_with_a_stray_prefix_is_refuse_and_ask(self) -> None:
        self.assertPackedValueIsRefused("packed-prefixed", "xx" + "a" * 40, "is packed at a value that is not an object id")

    def test_an_uppercase_packed_object_id_is_refuse_and_ask(self) -> None:
        """Git writes lowercase hex, so an uppercase value is a value this module cannot confirm
        names the object Git would resolve -- and 40 characters made it LOOK well-formed."""
        self.assertPackedValueIsRefused("packed-uppercase", "A" * 40, "is packed at a value that is not an object id")

    def test_a_malformed_packed_value_is_refused_even_with_an_empty_object_store(self) -> None:
        """The distinguishing input that separates the two layers of this fix. With no objects on
        disk the unborn-branch proof has nothing to object to, so ONLY the object-id check can
        refuse -- which is what makes it load-bearing rather than redundant with the proof."""
        target = self.repo("packed-truncated-bare", readme=True)
        self.write_packed_refs(target, f"{'a' * 39} refs/heads/main")

        git_fd = os.open(target / ".git", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.addCleanup(os.close, git_fd)
        self.assertIsNone(rc._first_evidence_of_objects(git_fd), "the object store must really be empty")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "is packed at a value that is not an object id")
        # Positive control: a 40-character value in the same file and the same empty store resolves
        # far enough to name the missing object instead, so the refusal above is the LENGTH.
        self.write_packed_refs(target, f"{'a' * 40} refs/heads/main")
        second = self.assertVerdict(target, "refuse-and-ask")
        self.assertAmbiguity(second, "commit-history", f"commit {'a' * 40} is not a loose object")
        self.assertFalse(any("not an object id" in item["detail"] for item in second["ambiguities"]), second)

    def test_a_reftable_backend_stops_an_unborn_branch_from_being_proven(self) -> None:
        """A backend this module does not read could hold the branch, so its absence from the loose
        and packed surfaces proves nothing -- not even in an otherwise empty repository."""
        target = self.repo("reftable-unborn", readme=True)
        (target / ".git" / "reftable").mkdir()

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "reftable backend is not read offline")
        # The unborn claim must be blocked BY NAME, not merely outvoted by the line above: the
        # verdict is refuse-and-ask either way, so only this second detail can tell a reader that
        # the branch's absence from the loose and packed surfaces proved nothing.
        self.assertAmbiguity(result, "ref-surface", "refs/heads/main is in neither ref storage, and the unread .git/reftable could hold it")
        # Positive control: the identical repository without the reftable directory has a branch
        # this module CAN prove unborn, so the refusal is the unread backend and nothing else.
        (target / ".git" / "reftable").rmdir()
        self.assertVerdict(target, "greenfield")

    def test_a_branch_packed_at_two_different_object_ids_is_refuse_and_ask(self) -> None:
        """Taking the last matching line was a silent choice between two commits."""
        target = self.occupied_repository("packed-twice")
        oid = self.unpack_branch(target)
        self.write_packed_refs(target, f"{'0' * 40} refs/heads/main", f"{oid} refs/heads/main")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "is packed at 2 different object ids")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: one line, the same id, the same channel -- resolves and reports both.
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_loose_branch_also_packed_at_another_id_is_named(self) -> None:
        """Git resolves the loose value and so does this walk, but a packed entry at a DIFFERENT
        id names a second commit that no proof over the loose one can rule out."""
        target = self.repo("stale-packed", commit=True, readme=True)
        oid = (target / ".git" / "refs" / "heads" / "main").read_text(encoding="utf-8").strip()
        self.write_packed_refs(target, f"{'0' * 40} refs/heads/main")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", f"refs/heads/main is also packed at {'0' * 40}")
        # Positive control: the same packed line at the SAME id as the loose ref is consistent and
        # greenfield, so the ambiguity is the disagreement and not the packed entry's existence.
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertVerdict(target, "greenfield")

    def test_an_unparsable_packed_refs_line_names_the_line_number(self) -> None:
        target = self.occupied_repository("packed-unparsable")
        oid = self.unpack_branch(target)
        self.write_packed_refs(target, f"{oid}\trefs/heads/main")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "packed-refs line 2 is not '<object id> <ref name>'")
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertSeesTheCommittedSurfaces(target)

    def test_an_emptied_packed_refs_does_not_make_a_packed_branch_unborn(self) -> None:
        """The ref surface goes silent while the history stays on disk. Absence of the branch from
        both storages is only a proof when nothing in the repository contradicts it."""
        target = self.occupied_repository("packed-emptied")
        oid = self.unpack_branch(target)
        (target / ".git" / "packed-refs").write_text("", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"refs/heads/main is unborn but {GIT_OBJECTS}/")
        self.assertAmbiguity(result, "commit-history", "is not empty")
        named = next(item["detail"] for item in result["ambiguities"] if GIT_OBJECTS in item["detail"])
        fanout = named.split(f"{GIT_OBJECTS}/", 1)[1].split(" ", 1)[0]
        self.assertTrue((target / ".git" / "objects" / fanout).is_dir(), f"{named} must name a real object directory")
        # Positive control: the branch line back in the same file resolves and reports both
        # surfaces, so the refusal is the emptied ref surface and not an unreadable repository.
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_head_pointing_at_a_ref_in_neither_storage_is_refuse_and_ask(self) -> None:
        """`git update-ref -d` leaves this shape: HEAD names a branch that no storage holds while
        every commit is still in `objects`."""
        target = self.occupied_repository("deleted-branch")
        oid = self.unpack_branch(target)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "refs/heads/main is unborn but")
        # Positive control: the same object id written back to the same loose path resolves.
        (target / ".git" / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        self.assertSeesTheCommittedSurfaces(target)

    def test_an_unborn_branch_with_a_staged_object_is_refuse_and_ask(self) -> None:
        """`git init && git add` leaves one blob and no commit. Something happened here, so the
        emptiest verdict this module may reach is a question."""
        target = self.repo("staged", readme=True)
        oid = write_blob(target / ".git")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"{GIT_OBJECTS}/{oid[:2]} is not empty")
        self.assertAmbiguity(result, "commit-history", oid[2:])
        # Positive control: removing that one object -- leaving the now-empty fanout directory in
        # place -- is greenfield, so the refusal is the object and not the directory.
        object_path(target / ".git", oid).unlink()
        self.assertTrue((target / ".git" / "objects" / oid[:2]).is_dir(), "the empty fanout directory stays")
        self.assertVerdict(target, "greenfield")

    def test_a_non_directory_in_the_object_store_is_refuse_and_ask(self) -> None:
        target = self.repo("loose-pack", readme=True)
        (target / ".git" / "objects" / "pack").mkdir()
        (target / ".git" / "objects" / "pack" / "pack-abc.pack").write_bytes(b"PACK")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"{GIT_OBJECTS}/pack is not empty: pack-abc.pack")
        # Positive control: `git init` leaves `objects/pack` present and EMPTY, and that is
        # greenfield, so the ambiguity is the packfile rather than the directory.
        (target / ".git" / "objects" / "pack" / "pack-abc.pack").unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_packfile_beside_a_resolved_commit_is_refuse_and_ask(self) -> None:
        """The object-store proof guards the UNBORN branch only, so this is the resolved path's
        version of the same hole: `git gc && git commit --amend` leaves the amended commit loose
        and parentless while the previous history sits in a packfile the walk never reads."""
        target = self.repo("amended", commit=True, readme=True)
        (target / ".git" / "objects" / "pack").mkdir()
        (target / ".git" / "objects" / "pack" / "pack-0123.pack").write_bytes(b"PACK")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", "objects/pack is not empty, so commits this walk did not read may exist")
        self.assertAmbiguity(result, "commit-history", "pack-0123.pack")
        # Positive control: `git init` leaves `objects/pack` present and EMPTY, and the same
        # repository in that shape is greenfield, so the refusal is the packfile itself.
        (target / ".git" / "objects" / "pack" / "pack-0123.pack").unlink()
        self.assertTrue((target / ".git" / "objects" / "pack").is_dir(), "the empty pack directory stays")
        self.assertVerdict(target, "greenfield")

    def test_an_unborn_branch_with_a_reflog_is_refuse_and_ask(self) -> None:
        """`git init` writes no reflog, so one exists only because a ref was updated -- even after
        the objects it pointed at were pruned away."""
        target = self.repo("reflogged", readme=True)
        (target / ".git" / "logs").mkdir()
        (target / ".git" / "logs" / "HEAD").write_text(f"{'0' * 40} {'1' * 40} A <a@example.invalid> 0 +0000\tcommit\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"{GIT_LOGS} is not empty: HEAD")
        # Positive control: with the reflog removed the identical repository is greenfield.
        (target / ".git" / "logs" / "HEAD").unlink()
        (target / ".git" / "logs").rmdir()
        self.assertVerdict(target, "greenfield")

    def test_an_absent_object_store_is_not_proof_of_emptiness(self) -> None:
        target = self.repo("storeless", readme=True)
        (target / ".git" / "objects" / "info").rmdir()
        (target / ".git" / "objects").rmdir()

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"{GIT_OBJECTS} is absent")
        (target / ".git" / "objects" / "info").mkdir(parents=True)
        self.assertVerdict(target, "greenfield")

    def test_an_object_store_path_that_is_a_file_names_the_malformation(self) -> None:
        target = self.repo("store-is-file", readme=True)
        (target / ".git" / "objects" / "info").rmdir()
        (target / ".git" / "objects").rmdir()
        (target / ".git" / "objects").write_text("not a directory\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f"{GIT_OBJECTS} is not a directory")
        # Positive control: the same path as a real empty object store is greenfield, so the
        # ambiguity is the node type and not the path being consulted at all.
        (target / ".git" / "objects").unlink()
        (target / ".git" / "objects" / "info").mkdir(parents=True)
        self.assertVerdict(target, "greenfield")

    def test_an_oversized_object_store_listing_refuses_rather_than_concluding_empty(self) -> None:
        target = self.repo("wide-store", readme=True)

        with mock.patch.object(rc, "MAX_OBJECT_STORE_ENTRIES", 0):
            bounded = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(bounded, "commit-history", "holds more than 0 entries")
        # Positive control: the SAME repository under the shipped bound is greenfield, so the
        # refusal is the ceiling and not the store's contents.
        self.assertVerdict(target, "greenfield")

    def test_a_packed_refs_that_is_not_a_regular_file_is_refuse_and_ask(self) -> None:
        """A FIFO or a directory at `packed-refs` used to empty the whole packed ref surface,
        because the reader returned the same None it returns for an absent file."""
        target = self.occupied_repository("packed-fifo")
        oid = self.unpack_branch(target)
        os.mkfifo(target / ".git" / "packed-refs")

        result = self.assertVerdictWithoutBlocking(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "packed-refs is not a regular file")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: a real packed-refs at the same path resolves the same branch.
        (target / ".git" / "packed-refs").unlink()
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_refs_path_that_is_a_regular_file_is_refuse_and_ask(self) -> None:
        """`.git/refs` is a directory Git owns. A plain file there means the loose ref surface is
        malformed, not that this repository has no loose refs -- the same distinction the CANDIDATE
        classifier makes in the other direction, where a plain `docs` really does prove `docs/adr`
        cannot exist."""
        target = self.occupied_repository("refs-is-file")
        oid = self.unpack_branch(target)
        for child in sorted((target / ".git" / "refs").rglob("*"), reverse=True):
            child.rmdir()
        (target / ".git" / "refs").rmdir()
        (target / ".git" / "refs").write_text("not a directory\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", f"{GIT_REFS} is not a directory")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: the same object id under a real `refs` tree resolves and reports both
        # surfaces, so the refusal is the node type rather than a repository with no refs.
        (target / ".git" / "refs").unlink()
        (target / ".git" / "refs" / "heads").mkdir(parents=True)
        (target / ".git" / "refs" / "heads" / "main").write_text(f"{oid}\n", encoding="utf-8")
        self.assertSeesTheCommittedSurfaces(target)

    def test_an_absent_refs_tree_is_still_a_readable_ref_surface(self) -> None:
        """The distinguishing input for the rule above: a fully packed repository legitimately has
        no `refs` tree, so ENOENT must keep meaning absence while ENOTDIR does not."""
        target = self.occupied_repository("refs-absent")
        oid = self.unpack_branch(target)
        for child in sorted((target / ".git" / "refs").rglob("*"), reverse=True):
            child.rmdir()
        (target / ".git" / "refs").rmdir()
        self.write_packed_refs(target, f"{oid} refs/heads/main")

        self.assertFalse((target / ".git" / "refs").exists(), "the loose ref tree is gone on purpose")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_loose_ref_that_vanishes_mid_walk_is_not_an_empty_ref_surface(self) -> None:
        """Catching `FileNotFoundError` around the WALK as well as the `refs` open reported "no
        loose refs" for any disappearance underneath it. Patched because a real race cannot be
        scheduled, and the patch stands in for the ENOTDIR path the test above covers on disk."""
        target = self.occupied_repository("racing-refs")

        def vanish(*_args, **_kwargs):
            raise FileNotFoundError(errno.ENOENT, "ref disappeared")
            yield  # pragma: no cover - generator protocol only

        with mock.patch.object(rc, "_walk_loose_refs", vanish):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "ref surface is not readable")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: unpatched, the identical repository reads its loose ref and reports
        # both committed surfaces, so the refusal is the failed walk and not the fixture.
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_hooks_path_that_is_a_regular_file_is_refuse_and_ask(self) -> None:
        target = self.repo("hooks-is-file", commit=True, readme=True)
        for sample in sorted((target / ".git" / "hooks").iterdir()):
            sample.unlink()
        (target / ".git" / "hooks").rmdir()
        (target / ".git" / "hooks").write_text("not a directory\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "undetermined-surface", ".git/hooks is not a directory")
        # Positive control: a real hooks directory holding a real hook is a named occupied hook
        # surface, so the ambiguity is the node type and not a channel that never reports.
        (target / ".git" / "hooks").unlink()
        (target / ".git" / "hooks").mkdir()
        (target / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "hook", ".git/hooks/pre-commit")

    def test_a_multi_line_head_is_refuse_and_ask(self) -> None:
        target = self.repo("multiline-head", commit=True, readme=True, head="ref: refs/heads/main\nref: refs/heads/other\n")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "head-form", "HEAD is not a single line")
        # Positive control: the first line alone, through the same file, is greenfield -- which is
        # what makes taking the first line of a two-line HEAD a silent choice.
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_branch_name_with_a_control_character_is_refuse_and_ask(self) -> None:
        target = self.repo("odd-branch", commit=True, readme=True, head="ref: refs/heads/ma\x01in\n")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "head-form", "names an unusable branch")
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_head_that_is_not_a_regular_file_is_a_named_refusal(self) -> None:
        target = self.repo("head-is-dir", commit=True, readme=True)
        (target / ".git" / "HEAD").unlink()
        (target / ".git" / "HEAD").mkdir()

        self.assertRefusedToInspect(target, "HEAD is not a regular file")

        # Positive control: the same path as a real symref file classifies at exit 0.
        (target / ".git" / "HEAD").rmdir()
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_an_undetermined_ref_surface_can_never_be_silent(self) -> None:
        """Defence in depth on this ticket's own defect class. If any future `REF_UNDETERMINED`
        return forgets to name its reason, the verdict must still be a question."""
        # An UNBORN repository, so the control below can actually reach greenfield: a committed one
        # would be refused by the object-store proof and prove nothing about this guard.
        target = self.repo("silent-undetermined", readme=True)

        with mock.patch.object(rc, "resolve_sole_ref", lambda *_args: (rc.REF_UNDETERMINED, None)):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "could not be resolved and no reason was recorded")
        # Positive control on the same patch channel: a patched UNBORN state in this same
        # repository still reaches greenfield, so the refusal above is the undetermined state and
        # not the act of patching the resolver.
        with mock.patch.object(rc, "resolve_sole_ref", lambda *_args: (rc.REF_UNBORN, None)):
            self.assertVerdict(target, "greenfield")

    def test_a_resolved_ref_without_an_object_id_is_named_rather_than_crashing(self) -> None:
        target = self.repo("resolved-without-id", readme=True)

        with mock.patch.object(rc, "resolve_sole_ref", lambda *_args: (rc.REF_RESOLVED, None)):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "resolved without an object id")
        with mock.patch.object(rc, "resolve_sole_ref", lambda *_args: (rc.REF_UNBORN, None)):
            self.assertVerdict(target, "greenfield")

    def test_the_three_ref_states_are_distinct(self) -> None:
        """Two of them collapsing into one string is the defect expressed as a constant."""
        self.assertEqual(len({rc.REF_RESOLVED, rc.REF_UNBORN, rc.REF_UNDETERMINED}), 3)

    def assertLooseBranchIsRefused(self, target: Path, oid: str, fragment: str) -> None:
        """A present-but-unreadable loose branch file is UNDETERMINED, never unborn.

        The positive control is the same path holding the same object id as an ordinary file: it
        resolves and names both committed surfaces, so the refusal is attributable to the hazard
        rather than to a branch that pointed at nothing.
        """
        result = self.assertVerdictWithoutBlocking(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", f"refs/heads/main is not readable: {fragment}")
        # The surfaces are INVISIBLE while the branch is unresolved, which is exactly why reading
        # the unreadable file as an unborn branch reported greenfield with nothing in the list.
        self.assertEqual(result["occupied"], [], result)
        self.assertFalse(
            any("unborn" in item["detail"] for item in result["ambiguities"]),
            f"an unreadable branch file is not an unborn branch: {result['ambiguities']}",
        )
        branch = target / ".git" / "refs" / "heads" / "main"
        branch.unlink()
        branch.write_text(f"{oid}\n", encoding="utf-8")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_loose_branch_file_that_is_a_symlink_is_not_read_through(self) -> None:
        """A branch file pointing OUT of the checkout. Reading it would resolve a commit from
        another tree, and calling it unborn would earn greenfield for a repository with history."""
        target = self.occupied_repository("linked-branch")
        branch = target / ".git" / "refs" / "heads" / "main"
        oid = branch.read_text(encoding="utf-8").strip()
        outside = self.tmp_root / "outside-branch"
        outside.write_text(f"{oid}\n", encoding="utf-8")
        branch.unlink()
        branch.symlink_to(outside)

        self.assertLooseBranchIsRefused(target, oid, errno.errorcode[errno.ELOOP])
        # The decoy really was readable and really did name this repository's own commit, so the
        # refusal is `O_NOFOLLOW` rather than an ENOENT from a link pointing at nothing.
        self.assertEqual(outside.read_text(encoding="utf-8").strip(), oid)

    def test_a_loose_branch_file_that_is_a_fifo_is_refused_rather_than_read(self) -> None:
        """This test HANGS rather than fails if the opener ever drops `O_NONBLOCK`, and reports a
        greenfield repository if a FIFO's empty read is mistaken for an absent branch."""
        target = self.occupied_repository("fifo-branch")
        branch = target / ".git" / "refs" / "heads" / "main"
        oid = branch.read_text(encoding="utf-8").strip()
        branch.unlink()
        os.mkfifo(branch)

        self.assertLooseBranchIsRefused(target, oid, "refs/heads/main is not a regular file (other)")

    def test_an_oversized_loose_branch_file_is_refused_rather_than_truncated(self) -> None:
        """The padding is deliberately WHITESPACE: a reader that truncates at its limit instead of
        refusing would strip the tail and resolve the id anyway, so only a refusal distinguishes
        `this file is longer than I will read` from `this is what the file says`."""
        target = self.occupied_repository("oversized-branch")
        branch = target / ".git" / "refs" / "heads" / "main"
        oid = branch.read_text(encoding="utf-8").strip()
        branch.write_text(f"{oid}\n" + " " * 5000 + "x" * 100, encoding="utf-8")

        self.assertLooseBranchIsRefused(target, oid, errno.errorcode[errno.EFBIG])

    def test_an_unreadable_reftable_probe_leaves_the_ref_surface_undetermined(self) -> None:
        """The reftable probe's own failure arm. `.git/reftable` is a single component, so nothing
        on disk makes its `lstat` fail once `.git` is open -- but concluding `there is no reftable
        backend` from a probe that failed is the same false-empty one link earlier, so the arm has
        to exist and has to be observable."""
        target = self.occupied_repository("reftable-unreadable")
        real_lstat_at = rc._lstat_at

        def lstat_that_fails_for_the_reftable(dir_fd, relative):
            if relative == "reftable":
                raise rc.UndeterminedPath("reftable: EIO")
            return real_lstat_at(dir_fd, relative)

        with mock.patch.object(rc, "_lstat_at", lstat_that_fails_for_the_reftable):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "ref surface is not readable: reftable: EIO")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: unpatched, the identical repository resolves the same branch and names
        # both committed surfaces, so the refusal is the failed probe and not the repository.
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_non_utf8_head_names_itself(self) -> None:
        target = self.repo("head-not-utf8", commit=True, readme=True)
        (target / ".git" / "HEAD").write_bytes(b"ref: refs/heads/ma\xffin\n")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "head-form", "HEAD is not UTF-8")
        # Positive control: the same file as decodable UTF-8 naming the same branch is greenfield,
        # so the ambiguity is the decode and not the presence of a HEAD at all.
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_every_unusable_branch_shape_is_refused_before_it_is_looked_up(self) -> None:
        """The name this module looks up has to be the name Git would resolve. A branch Git itself
        rejects is looked up under a name no ref can have, finds nothing, and would then be read as
        an unborn branch -- a greenfield claim about a HEAD nobody can interpret."""
        target = self.repo("unusable-branches", readme=True)
        head = target / ".git" / "HEAD"
        for spelling in ("refs/heads/../../../etc", "refs/heads/ma in", "refs/heads/", "refs/heads//x", "refs/heads/."):
            with self.subTest(branch=spelling):
                head.write_text(f"ref: {spelling}\n", encoding="utf-8")

                result = self.assertVerdict(target, "refuse-and-ask")

                self.assertAmbiguity(result, "head-form", "names an unusable branch")
        # Positive control: an ordinary branch symref in the same file and the same repository is
        # greenfield, so each refusal above is the branch NAME rather than the fixture.
        head.write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_ref_subdirectory_is_named_rather_than_walked_into(self) -> None:
        """A symlinked directory under `.git/refs` is reported as the entry it is. Following it
        would pull ref names from another tree into this repository's ref list."""
        target = self.repo("linked-ref-dir", commit=True, readme=True)
        git = target / ".git"
        oid = (git / "refs" / "heads" / "main").read_text(encoding="utf-8").strip()
        outside = self.tmp_root / "outside-heads"
        outside.mkdir()
        (outside / "sneaky").write_text(f"{oid}\n", encoding="utf-8")
        (git / "refs" / "heads" / "other").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "1 refs beyond refs/heads/main: refs/heads/other")
        # Containment, asserted twice: no name from the link's target enters the ref list, and the
        # link does not empty or invalidate the whole loose surface either.
        self.assertFalse(any("sneaky" in item["detail"] for item in result["ambiguities"]), result)
        self.assertFalse(any("not readable" in item["detail"] for item in result["ambiguities"]), result)
        # Positive control: a REAL file at that path is named the same way, and removing the entry
        # returns the identical repository to greenfield.
        (git / "refs" / "heads" / "other").unlink()
        (git / "refs" / "heads" / "other").write_text(f"{oid}\n", encoding="utf-8")
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "ref-surface", "refs/heads/other")
        (git / "refs" / "heads" / "other").unlink()
        self.assertVerdict(target, "greenfield")

    def test_loose_refs_nested_past_the_bound_refuse_rather_than_recursing(self) -> None:
        """The bound is headroom over any ref layout Git writes, so the distinguishing input is the
        patched constant -- exactly as for the committed walk. Exceeding it is a REFUSAL: an
        unbounded recursion would raise `RecursionError`, which is not a read failure, and would
        lose the whole classification instead of naming one ref tree."""
        target = self.occupied_repository("deep-refs")

        with mock.patch.object(rc, "MAX_REF_WALK_DEPTH", 0):
            bounded = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(bounded, "ref-surface", "nests deeper than 0 levels")
        self.assertEqual(bounded["occupied"], [], bounded)
        # Positive control: the SAME repository under the shipped bound resolves its branch and
        # names both committed surfaces, so the refusal is the ceiling and not the ref tree.
        self.assertSeesTheCommittedSurfaces(target)

    def test_more_loose_refs_than_the_bound_refuse_rather_than_concluding_anything(self) -> None:
        target = self.occupied_repository("many-refs")

        with mock.patch.object(rc, "MAX_REF_WALK_ENTRIES", 0):
            bounded = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(bounded, "ref-surface", "holds more than 0 refs")
        self.assertEqual(bounded["occupied"], [], bounded)
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_peeled_packed_refs_line_is_not_a_malformation(self) -> None:
        """`git pack-refs` writes a `^<peeled id>` line under every annotated tag. Reading one as a
        malformed pair would refuse every repository that has ever tagged a release, and dropping
        the skip in the other direction would silently empty the packed surface."""
        target = self.repo("peeled-tag", commit=True, readme=True)
        self.write_packed_refs(target, f"{'1' * 40} refs/tags/v1", f"^{'2' * 40}")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "1 refs beyond refs/heads/main: refs/tags/v1")
        self.assertFalse(
            any("packed-refs line" in item["detail"] for item in result["ambiguities"]),
            f"a peeled line is a shape Git writes, not a malformation: {result['ambiguities']}",
        )
        # Negative control on the same channel: a line that really IS malformed names its number,
        # so the assertion above is not passing because nothing is ever reported.
        self.write_packed_refs(target, f"{'1' * 40}\trefs/tags/v1")
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "ref-surface", "packed-refs line 2 is not")
        # Positive control: with the packed file gone the identical repository is greenfield.
        (target / ".git" / "packed-refs").unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_packed_refs_line_with_no_ref_name_names_the_line(self) -> None:
        """An id with no name is not a pair. Accepting it would put a nameless ref in the list,
        where it is reported as a foreign ref and blames the wrong thing."""
        target = self.occupied_repository("packed-nameless")
        oid = self.unpack_branch(target)
        self.write_packed_refs(target, f"{oid} refs/heads/main", f"{oid} ")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "ref-surface", "packed-refs line 3 is not '<object id> <ref name>'")
        self.assertEqual(result["occupied"], [], result)
        self.assertFalse(any("refs beyond" in item["detail"] for item in result["ambiguities"]), result)
        # Positive control: the branch line alone, in the same file, resolves and names both
        # committed surfaces, so the refusal is the nameless line and nothing else.
        self.write_packed_refs(target, f"{oid} refs/heads/main")
        self.assertSeesTheCommittedSurfaces(target)

    def test_a_plain_file_in_the_object_store_is_named_evidence(self) -> None:
        """`git commit-graph write` leaves exactly this shape. The store's top level holds fanout
        DIRECTORIES; a file there is something that already happened in this repository, and
        descending into it instead would blame a vanished directory for a file that is right
        there."""
        target = self.repo("commit-graph", readme=True)
        (target / ".git" / "objects" / "commit-graph").write_bytes(b"CGPH")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", ".git/objects/commit-graph is a file")
        # Positive control: with that one file gone the identical repository is greenfield, so the
        # refusal is the file rather than the store being consulted at all.
        (target / ".git" / "objects" / "commit-graph").unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_object_fanout_is_named_rather_than_followed(self) -> None:
        """The unborn-branch proof's version of the fanout custody guard: a symlinked fanout is
        EVIDENCE that something is here, and following it would count objects from another tree."""
        target = self.repo("linked-fanout-unborn", readme=True)
        outside = self.tmp_root / "outside-fanout"
        outside.mkdir()
        (outside / ("e" * 38)).write_bytes(b"x")
        (target / ".git" / "objects" / "ab").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", ".git/objects/ab is a symlink")
        self.assertFalse(
            any(errno.errorcode[errno.ENOENT] in item["detail"] for item in result["ambiguities"]),
            f"the refusal must name the symlink, not an absence: {result['ambiguities']}",
        )
        # Positive control: the same directory moved INSIDE the store is named as a non-empty
        # fanout, and with it gone the repository is greenfield -- so the refusal is the link.
        (target / ".git" / "objects" / "ab").unlink()
        outside.rename(target / ".git" / "objects" / "ab")
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "commit-history", ".git/objects/ab is not empty")
        (target / ".git" / "objects" / "ab" / ("e" * 38)).unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_fanout_directory_that_vanishes_mid_read_is_not_an_empty_store(self) -> None:
        """`git gc` can prune a fanout directory between the listing and the descent. Skipping it
        would report the store empty while the objects it held are unaccounted for, so the
        disappearance is raised as UNDETERMINED rather than absorbed by the `objects is absent`
        branch one frame up. Patched because a real race cannot be scheduled."""
        target = self.repo("vanishing-fanout", readme=True)
        oid = write_blob(target / ".git")
        real_descend = rc._descend

        @contextlib.contextmanager
        def descend_where_the_fanout_vanishes(dir_fd, components):
            name = components[-1] if components else ""
            if len(name) == 2 and all(character in "0123456789abcdef" for character in name):
                raise FileNotFoundError(errno.ENOENT, "the fanout directory was pruned mid-read")
            with real_descend(dir_fd, components) as fd:
                yield fd

        with mock.patch.object(rc, "_descend", descend_where_the_fanout_vanishes):
            result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", f".git/objects/{oid[:2]} changed while it was read")
        self.assertFalse(any("objects is absent" in item["detail"] for item in result["ambiguities"]), result)
        # Positive control: unpatched, the same store names the staged object through the same
        # channel, so the refusal is the disappearance and not a store that reports nothing.
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "commit-history", f".git/objects/{oid[:2]} is not empty")

    def test_a_reflog_path_that_is_a_regular_file_names_the_malformation(self) -> None:
        """`.git/logs` is a directory Git owns. A plain file there means the reflog surface is
        malformed, not that this repository never updated a ref -- and `git init` writes no reflog
        at all, so absence has to keep its own separate meaning."""
        target = self.repo("logs-is-file", readme=True)
        (target / ".git" / "logs").write_text("not a directory\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", ".git/logs is not a directory")
        # Positive control: with the path absent -- the shape `git init` leaves -- the identical
        # repository is greenfield, so the refusal is the node type and not the path being read.
        (target / ".git" / "logs").unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_reflog_directory_is_not_read_through(self) -> None:
        target = self.repo("logs-is-symlink", readme=True)
        outside = self.tmp_root / "outside-logs"
        outside.mkdir()
        (outside / "HEAD").write_text("x\n", encoding="utf-8")
        (target / ".git" / "logs").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", ".git/logs is not readable: logs is a symlink")
        # The decoy is a real reflog: moved inside `.git` it is named as a non-empty one, and an
        # empty directory in the same place is greenfield -- so the refusal is the link itself.
        (target / ".git" / "logs").unlink()
        outside.rename(target / ".git" / "logs")
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "commit-history", ".git/logs is not empty: HEAD")
        (target / ".git" / "logs" / "HEAD").unlink()
        self.assertVerdict(target, "greenfield")

    def test_a_pack_path_that_is_a_regular_file_names_the_malformation(self) -> None:
        """The resolved-commit walk reads loose objects only, so `objects/pack` is consulted to say
        whether unread history exists. A plain file there answers neither yes nor no."""
        target = self.repo("pack-is-file", commit=True, readme=True)
        (target / ".git" / "objects" / "pack").write_text("not a directory\n", encoding="utf-8")

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", ".git/objects/pack is not a directory")
        # Positive control: the same path as a real empty pack directory -- and as no path at all,
        # which is also a shape on disk -- is greenfield.
        (target / ".git" / "objects" / "pack").unlink()
        (target / ".git" / "objects" / "pack").mkdir()
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_pack_directory_is_not_read_through(self) -> None:
        target = self.repo("pack-is-symlink", commit=True, readme=True)
        outside = self.tmp_root / "outside-pack"
        outside.mkdir()
        (outside / "pack-0123.pack").write_bytes(b"PACK")
        (target / ".git" / "objects" / "pack").symlink_to(outside, target_is_directory=True)

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-history", ".git/objects/pack is not readable: pack is a symlink")
        # The decoy is a real packfile: inside the store it is named as unread history, and the
        # empty directory is greenfield -- so the refusal is the link and not an absent path.
        (target / ".git" / "objects" / "pack").unlink()
        outside.rename(target / ".git" / "objects" / "pack")
        self.assertAmbiguity(self.assertVerdict(target, "refuse-and-ask"), "commit-history", "pack-0123.pack")
        (target / ".git" / "objects" / "pack" / "pack-0123.pack").unlink()
        self.assertVerdict(target, "greenfield")


class TreeEntryModeTests(ClassifierTestCase):
    def test_an_unrecognized_tree_entry_mode_is_named_rather_than_skipped(self) -> None:
        """Only `mode == GIT_MODE_TREE` descends, so a directory-flavoured mode this walk does not
        recognize would leave every candidate beneath it unexamined and report nothing."""
        target = self.repo("odd-mode")
        git = target / ".git"
        self.commit_tree(target, write_tree(git, {"docs": (0o40755, build_tree(git, {"adr/0001-x.md": (BLOB_MODE, write_blob(git))}))}))

        result = self.assertVerdict(target, "refuse-and-ask")

        self.assertAmbiguity(result, "commit-tree", "HEAD:docs has mode 040755")
        self.assertEqual(result["occupied"], [], result)
        # Positive control: the identical subtree under the mode Git actually writes IS descended
        # and reports the occupied decision surface, so the refusal is the mode and not the shape.
        self.commit_tree(target, write_tree(git, {"docs": (TREE_MODE, build_tree(git, {"adr/0001-x.md": (BLOB_MODE, write_blob(git))}))}))
        self.assertOccupied(self.assertVerdict(target, "brownfield"), "decision", "HEAD:docs/adr")

    def test_every_mode_the_walk_interprets_is_a_mode_git_writes(self) -> None:
        self.assertEqual(rc.GIT_MODES, frozenset({TREE_MODE, GITLINK_MODE, SYMLINK_MODE, 0o100644, 0o100755}))
        self.assertNotIn(0o40755, rc.GIT_MODES)


class InspectionRefusalTests(ClassifierTestCase):
    def test_a_directory_without_git_is_refused_rather_than_classified(self) -> None:
        target = self.tmp_root / "plain"
        target.mkdir()
        (target / "README.md").write_text("# intent\n", encoding="utf-8")

        self.assertRefusedToInspect(target, ".git is absent")

        # Positive control: the identical directory with a `.git` classifies at exit 0, so
        # the refusal is the missing repository and not the target path itself.
        make_git(target)
        self.assertVerdict(target, "greenfield")

    def test_a_git_file_redirect_is_refused(self) -> None:
        target = self.tmp_root / "linked-worktree"
        target.mkdir()
        (target / ".git").write_text("gitdir: /elsewhere/.git/worktrees/w\n", encoding="utf-8")

        self.assertRefusedToInspect(target, ".git is not a directory")

        (target / ".git").unlink()
        make_git(target)
        self.assertVerdict(target, "greenfield")

    def test_a_symlinked_git_directory_is_refused_without_classifying_the_target(self) -> None:
        real = self.repo("real", commit=True, readme=True)
        target = self.tmp_root / "borrowed"
        target.mkdir()
        (target / ".git").symlink_to(real / ".git", target_is_directory=True)

        self.assertRefusedToInspect(target, ".git is a symlink")

        # The link target is a complete, classifiable repository -- proven by classifying it
        # directly -- so the refusal is the symlink guard rather than an unusable decoy.
        self.assertVerdict(real, "greenfield")

    def test_an_unsearchable_target_names_the_failed_git_inspection(self) -> None:
        """`.git` is stat-ed before it is opened, and a target that is readable but not SEARCHABLE
        fails that stat. Substituting a fabricated directory for a stat that failed would hand the
        rest of the module a `.git` nobody verified."""
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions, so the probe cannot fail")
        target = self.repo("unsearchable-root", commit=True, readme=True)
        target.chmod(0o400)
        self.addCleanup(target.chmod, 0o755)

        self.assertRefusedToInspect(target, f"cannot inspect .git: {errno.errorcode[errno.EACCES]}")

        # Positive control: searchable, the identical repository classifies at exit 0.
        target.chmod(0o755)
        self.assertVerdict(target, "greenfield")

    def test_an_unreadable_git_directory_names_the_failed_open(self) -> None:
        """The stat succeeds and the OPEN fails, which is the other half of the pair: the refusal
        has to name which step failed, or the human cannot tell a permission problem from a
        redirect."""
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions, so the probe cannot fail")
        target = self.repo("unreadable-git", commit=True, readme=True)
        (target / ".git").chmod(0o000)
        self.addCleanup((target / ".git").chmod, 0o755)

        self.assertRefusedToInspect(target, f"cannot open .git: {errno.errorcode[errno.EACCES]}")

        (target / ".git").chmod(0o755)
        self.assertVerdict(target, "greenfield")

    def test_an_absent_target_is_refused(self) -> None:
        self.assertRefusedToInspect(self.tmp_root / "missing", "target does not exist")

    def test_a_file_target_is_refused(self) -> None:
        target = self.tmp_root / "afile"
        target.write_text("x\n", encoding="utf-8")

        self.assertRefusedToInspect(target, "cannot open target")

    def test_a_git_directory_without_head_is_refused(self) -> None:
        target = self.repo("headless")
        (target / ".git" / "HEAD").unlink()

        self.assertRefusedToInspect(target, "HEAD")

        (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertVerdict(target, "greenfield")

    def test_a_relative_target_is_invalid_input(self) -> None:
        result, code = rc.classify_command(Path("relative/path"))

        self.assertEqual(code, rc.INVALID_INPUT_CODE, result)
        self.assertEqual(result["status"], "refused", result)
        self.assertTrue(any("absolute" in reason for reason in result["reasons"]), result)


class ExitCodeTests(ClassifierTestCase):
    """Implementation Decision 9's numbers are the contract, so these assert the LITERALS.
    Asserting the module's own constants instead cannot detect a renumbered code."""

    def test_every_completed_classification_exits_zero(self) -> None:
        greenfield = self.repo("green", commit=True, readme=True)
        brownfield = self.repo("brown", commit=True, readme=True)
        (brownfield / "AGENTS.md").write_text("# policy\n", encoding="utf-8")
        ask = self.repo("ask", commit=True, readme=True)
        (ask / "src").mkdir()

        for target, verdict in ((greenfield, "greenfield"), (brownfield, "brownfield"), (ask, "refuse-and-ask")):
            result, code = rc.classify_command(target)
            self.assertEqual((result["verdict"], code), (verdict, 0), result)

    def test_a_refusal_to_inspect_exits_three(self) -> None:
        target = self.tmp_root / "notarepo"
        target.mkdir()

        self.assertEqual(rc.classify_command(target)[1], 3)
        self.assertEqual(rc.INSPECT_REFUSAL_CODE, 3)

    def test_invalid_input_exits_two(self) -> None:
        self.assertEqual(rc.classify_command(Path("relative"))[1], 2)
        self.assertEqual(rc.INVALID_INPUT_CODE, 2)


class OutputContractTests(ClassifierTestCase):
    def test_output_is_canonical_and_byte_stable(self) -> None:
        target = self.repo("stable", commit=True, readme=True)
        (target / "src").mkdir()

        first = rc.canonical_bytes(self.classify(target))
        second = rc.canonical_bytes(self.classify(target))

        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))
        self.assertNotIn(b", ", first)
        keys = list(json.loads(first))
        self.assertEqual(keys, sorted(keys))

    def test_evidence_lists_are_sorted_for_diffability(self) -> None:
        target = self.repo("sorted", commit=True, readme=True)
        for relative in ("mise.toml", "AGENTS.md", ".gitlab-ci.yml", ".seeds"):
            (target / relative).write_text("x\n", encoding="utf-8")

        result = self.classify(target)

        pairs = [(item["surface"], item["path"]) for item in result["occupied"]]
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual(len(pairs), 4, result)

    def test_the_result_claims_no_authority(self) -> None:
        result = self.classify(self.repo("claims", commit=True, readme=True))

        self.assertEqual(set(result), rc.RESULT_KEYS)
        for name in result:
            self.assertFalse(
                any(token in name.lower() for token in rc.PROHIBITED_CLAIM_TOKENS),
                f"result key {name} claims authority the classifier cannot hold",
            )
        self.assertIn(result["verdict"], rc.VERDICTS)

    def test_classification_writes_nothing_to_the_target(self) -> None:
        target = self.repo("untouched", commit=True, readme=True)
        (target / "src").mkdir()
        before = snapshot(target)

        self.classify(target)

        self.assertEqual(snapshot(target), before)

    def test_main_writes_canonical_bytes_and_returns_the_exit_code(self) -> None:
        target = self.repo("cli", commit=True, readme=True)
        stream = io.StringIO()

        with redirect_stdout(_TextCapture(stream)):
            code = rc.main(["classify", "--target", str(target)])

        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["verdict"], "greenfield")
        self.assertEqual(payload["command"], "classify")
        self.assertEqual(payload["target"], str(target))

    def test_main_returns_the_refusal_code(self) -> None:
        target = self.tmp_root / "norepo"
        target.mkdir()
        stream = io.StringIO()

        with redirect_stdout(_TextCapture(stream)):
            code = rc.main(["classify", "--target", str(target)])

        self.assertEqual(code, rc.INSPECT_REFUSAL_CODE)
        self.assertEqual(json.loads(stream.getvalue())["status"], "refused")


class _TextCapture(io.TextIOBase):
    """A stdout stand-in that exposes `.buffer`, which `main` writes bytes to."""

    def __init__(self, sink: io.StringIO) -> None:
        self._sink = sink
        self.buffer = _ByteSink(sink)


class _ByteSink(io.RawIOBase):
    def __init__(self, sink: io.StringIO) -> None:
        self._sink = sink

    def write(self, data) -> int:  # noqa: ANN001 - matches the raw stream protocol
        self._sink.write(bytes(data).decode("utf-8"))
        return len(data)


if __name__ == "__main__":
    unittest.main()
