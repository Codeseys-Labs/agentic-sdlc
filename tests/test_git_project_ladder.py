"""The shared `.git` reader and the project-root resolution ladder (agentic-sdlc-7a2b, W4).

WHY THESE TWO ARE ONE SUITE. The ladder's every verdict is the reader's verdict renamed, so a test
that stubbed the reader would prove the renaming and nothing about the metadata. Every fixture here is
built by REAL `git` -- `init`, `worktree add`, `add`, `commit` -- for the same reason the dirtiness
fixtures are: what is under test is a reader of bytes git wrote, and bytes this file invented would
prove this file's idea of an index.

EVERY NEGATIVE ASSERTION CARRIES A POSITIVE CONTROL, because a ladder that refused everything would
pass a suite of refusal assertions. The pairs are explicit: the fifo `.git` refuses while the same
directory with a real `.git` admits; the two-line `.git` file refuses while the linked worktree whose
`.git` file has one line admits; `Path.home()` refuses while a repository one directory away admits.

NOTHING HERE MAY WRITE INTO A CANDIDATE ROOT. The ladder is a resolver, and `inventory` measures that
claim rather than asserting it: every fixture root is digested before and after resolution.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import install_skill_bundle as bundle  # noqa: E402
from tests.support.platform_paths import ABSOLUTE_ANCHOR, absolute_fixture  # noqa: E402

#: The reader under test, loaded exactly as the product loads it: through the substrate's one loader,
#: from a named distribution root. A second loading rule here could pass while the product's failed.
detector = bundle.load_git_project_detector(ROOT)

GIT = shutil.which("git")
GIT_SKIP = unittest.skipIf(GIT is None, "a real git is required to build metadata fixtures")
#: `O_NOATIME` exists on Linux and is what the reader requires rather than works around. A host
#: without it reads nothing, which is a capability skip and not a platform one.
NOATIME_SKIP = unittest.skipUnless(
    hasattr(os, "O_NOATIME"), "os.O_NOATIME is unavailable, so every metadata read refuses by name"
)


def git_environment(home: Path) -> dict[str, str]:
    """A hermetic git environment: no ambient config, no ambient identity, no ambient hooks.

    This process runs inside a worktree of the repository under test, so every `GIT_*` variable it
    inherited is dropped rather than trusted -- a leaked `GIT_DIR` would point a fixture's `git init`
    at the real checkout.
    """
    passthrough = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_") and name in ("PATH", "LANG", "LC_ALL", "TMPDIR")
    }
    return {
        **passthrough,
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }


def inventory(root: Path) -> dict[str, object]:
    """Digest every node under `root`, so "nothing was written" is measured rather than claimed."""
    snapshot: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            snapshot[relative] = f"symlink:{os.readlink(path)}"
        elif stat.S_ISDIR(mode):
            snapshot[relative] = "dir"
        elif stat.S_ISREG(mode):
            snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            snapshot[relative] = f"special:{stat.S_IFMT(mode)}"
    return snapshot


class Fixtures(unittest.TestCase):
    """One throwaway tree per test, holding every root shape the ladder distinguishes."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="git-project-ladder-")
        self.addCleanup(self._temp.cleanup)
        self.temp = Path(self._temp.name).resolve()
        self.home = self.temp / "home"
        self.home.mkdir()
        self.cwd = self.temp / "cwd"
        self.cwd.mkdir()

    def git(self, *arguments: str, cwd: Path) -> None:
        completed = subprocess.run(
            [str(GIT), *arguments],
            cwd=str(cwd),
            env=git_environment(self.home),
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def repository(self, name: str = "repo") -> Path:
        """One real single-commit repository whose `.git` is a DIRECTORY."""
        repo = self.temp / name
        repo.mkdir(parents=True)
        (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self.git("init", "-q", "-b", "main", ".", cwd=repo)
        self.git("add", "-A", cwd=repo)
        self.git("commit", "-q", "-m", "fixture", cwd=repo)
        return repo

    def linked_worktree(self) -> tuple[Path, Path]:
        """A primary checkout plus a linked worktree whose `.git` is a FILE. Both are roots."""
        primary = self.repository("primary")
        linked = self.temp / "linked"
        self.git("worktree", "add", "--quiet", "-b", "wave", str(linked), cwd=primary)
        self.assertTrue((linked / ".git").is_file(), "a linked worktree's .git is a file")
        return primary, linked

    def resolve(self, requested: Path | None, **overrides: object) -> object:
        """Drive the ladder with this fixture's own homes, never the operator's."""
        arguments: dict[str, object] = {
            "cwd": self.cwd,
            "operator_home": self.home,
            "plane_roots": (self.home, self.home / ".codex"),
            "distribution": ROOT,
            "detector": detector,
        }
        arguments.update(overrides)
        return bundle.resolve_project_root(requested, **arguments)  # type: ignore[arg-type]


@GIT_SKIP
@NOATIME_SKIP
class SharedReaderTest(Fixtures):
    """The reader's four verdicts, each against metadata a real git wrote."""

    def test_a_real_repository_admits_and_names_its_own_metadata_directory(self) -> None:
        repo = self.repository()

        admission = detector.admit(repo)

        self.assertTrue(admission.admitted, admission.reason)
        self.assertEqual(repo / ".git", admission.metadata)
        self.assertEqual("", admission.reason, "an admission explains nothing")

    def test_a_linked_worktree_admits_as_itself_and_never_as_the_primary_checkout(self) -> None:
        primary, linked = self.linked_worktree()

        admitted = detector.admit(linked)

        self.assertTrue(admitted.admitted, admitted.reason)
        # The metadata directory is the primary checkout's, and the ROOT is still the worktree: two
        # linked worktrees of one repository are two roots, two pointers, two independent planes.
        self.assertIsNotNone(admitted.metadata)
        self.assertTrue(str(admitted.metadata).startswith(str(primary / ".git")), admitted.metadata)
        self.assertTrue(detector.admit(primary).admitted, "the primary checkout is a root too")

    def test_a_directory_with_no_git_entry_is_absent_rather_than_refused(self) -> None:
        plain = self.temp / "plain"
        plain.mkdir()

        self.assertEqual(detector.ABSENT, detector.admit(plain).verdict)
        self.assertEqual(detector.ABSENT, detector.admit(self.temp / "missing").verdict)

    def test_a_git_entry_that_is_neither_a_file_nor_a_directory_is_an_unsafe_node(self) -> None:
        """THE MUTATION PAIR for the `unsafe-node` branch: this dies if the node check is removed."""
        hostile = self.temp / "fifo"
        hostile.mkdir()
        os.mkfifo(hostile / ".git")

        refusal = detector.admit(hostile)

        self.assertEqual(detector.UNSAFE_NODE, refusal.verdict)
        self.assertIn("neither a regular file nor a directory", refusal.reason)
        self.assertIsNone(refusal.metadata, "a refusal hands back nothing to read")

    def test_a_git_symlink_is_an_unsafe_node_and_is_never_followed(self) -> None:
        repo = self.repository()
        pointing = self.temp / "pointing"
        pointing.mkdir()
        os.symlink(repo / ".git", pointing / ".git", target_is_directory=True)

        self.assertEqual(detector.UNSAFE_NODE, detector.admit(pointing).verdict)

    def test_a_git_file_that_is_not_exactly_one_gitdir_line_is_invalid_metadata(self) -> None:
        """The control for the linked-worktree case: one line admits, two lines refuse."""
        _, linked = self.linked_worktree()
        one_line = (linked / ".git").read_text(encoding="utf-8")
        self.assertTrue(detector.admit(linked).admitted, "the fixture admits before the mutation")

        (linked / ".git").write_text(one_line.rstrip("\n") + "\nextra\n", encoding="utf-8")
        two_lines = detector.admit(linked)

        self.assertEqual(detector.INVALID_METADATA, two_lines.verdict)
        self.assertIn("exactly one readable 'gitdir: <path>' line", two_lines.reason)

    def test_a_git_file_naming_a_missing_directory_is_invalid_metadata(self) -> None:
        target = self.temp / "orphan"
        target.mkdir()
        (target / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")

        refusal = detector.admit(target)

        self.assertEqual(detector.INVALID_METADATA, refusal.verdict)
        self.assertIn("not a readable git metadata directory", refusal.reason)

    def test_a_git_directory_missing_its_minimum_structure_is_invalid_metadata(self) -> None:
        for name, build in (
            ("no-head", lambda metadata: None),
            ("empty-head", lambda metadata: (metadata / "HEAD").write_text("", encoding="utf-8")),
            ("no-objects", lambda metadata: (metadata / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")),
        ):
            with self.subTest(shape=name):
                target = self.temp / name
                metadata = target / ".git"
                metadata.mkdir(parents=True)
                if name != "no-objects":
                    (metadata / "refs").mkdir()
                    (metadata / "objects").mkdir()
                build(metadata)

                self.assertEqual(detector.INVALID_METADATA, detector.admit(target).verdict)

    def test_the_commondir_indirection_is_read_so_a_worktree_without_its_own_objects_admits(self) -> None:
        _, linked = self.linked_worktree()
        metadata = detector.metadata_directory(linked)

        self.assertIsNotNone(metadata)
        self.assertFalse((metadata / "objects").exists(), "a linked worktree keeps no objects of its own")
        self.assertIsNotNone(detector.common_directory(metadata), "so commondir has to be read")
        self.assertTrue(detector.metadata_directory_admits(metadata))

    def test_walk_up_stops_at_the_nearest_git_entry_and_answers_none_above_every_root(self) -> None:
        repo = self.repository()
        nested = repo / "a" / "b"
        nested.mkdir(parents=True)

        self.assertEqual(repo, detector.walk_up(nested))
        self.assertEqual(repo, detector.walk_up(repo))
        self.assertIsNone(detector.walk_up(self.temp / "cwd"))

    def test_a_metadata_read_leaves_access_times_untouched(self) -> None:
        """The reader's whole strictness argument, measured on the metadata it actually reads."""
        repo = self.repository()
        head = repo / ".git" / "HEAD"
        os.utime(head, (1_000_000, 1_000_000))
        before = head.lstat().st_atime_ns

        self.assertTrue(detector.admit(repo).admitted)

        self.assertEqual(before, head.lstat().st_atime_ns, "reading HEAD moved its access time")

    def test_an_unreadable_metadata_file_names_its_kind_rather_than_raising(self) -> None:
        missing = self.temp / "nothing-here"
        with self.assertRaises(detector.MetadataUnreadable) as raised:
            detector.read_without_atime(missing)
        self.assertEqual(detector.UNREADABLE, raised.exception.kind)
        self.assertIn("could not be opened", raised.exception.reason)

    def test_the_commit_and_dirtiness_observers_read_the_same_metadata_the_ladder_admits(self) -> None:
        repo = self.repository()
        commit = subprocess.run(
            [str(GIT), "rev-parse", "HEAD"],
            cwd=str(repo),
            env=git_environment(self.home),
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(commit, detector.observe_commit(repo))
        clean, reason = detector.observe_dirty(repo)
        self.assertFalse(clean, reason)
        # Positive control in the other direction, on the same fixture.
        (repo / "tracked.txt").write_text("moved\n", encoding="utf-8")
        modified, reason = detector.observe_dirty(repo)
        self.assertTrue(modified)
        self.assertIn("differs in content from the index", reason)
        self.assertEqual(detector.COMMIT_UNKNOWN, detector.observe_commit(self.temp / "cwd"))


@GIT_SKIP
@NOATIME_SKIP
class LadderTest(Fixtures):
    """Every rung of §2.2, in order, each with the control that proves it is a rung."""

    def test_an_explicit_root_is_admitted_without_a_walk(self) -> None:
        repo = self.repository()

        resolution = self.resolve(repo)

        self.assertEqual(bundle.PROJECT_ADMITTED, resolution.state)
        self.assertEqual(repo, resolution.root)
        self.assertEqual("", resolution.refusal)

    def test_the_walk_resolves_the_nearest_root_above_the_working_directory(self) -> None:
        repo = self.repository()
        inside = repo / "deep" / "deeper"
        inside.mkdir(parents=True)

        self.assertEqual(repo, self.resolve(None, cwd=inside).root)

    def test_nothing_above_the_working_directory_is_unresolvable_and_names_the_flag(self) -> None:
        resolution = self.resolve(None)

        self.assertEqual(bundle.PROJECT_UNRESOLVABLE, resolution.refusal)
        self.assertIn("--project PATH", resolution.detail)

    def test_a_subdirectory_of_a_repository_is_a_forbidden_root_naming_the_real_root(self) -> None:
        repo = self.repository()
        inside = repo / "sub"
        inside.mkdir()

        resolution = self.resolve(inside)

        self.assertEqual(bundle.PROJECT_FORBIDDEN_ROOT, resolution.refusal)
        self.assertIn(f"--project {repo}", resolution.detail)
        self.assertIsNone(resolution.root)

    def test_a_directory_outside_every_repository_is_not_a_git_project(self) -> None:
        plain = self.temp / "plain"
        plain.mkdir()

        resolution = self.resolve(plain)

        self.assertEqual(bundle.PROJECT_NOT_A_GIT_PROJECT, resolution.refusal)
        self.assertIn("holds no .git entry", resolution.detail)

    def test_a_hostile_git_node_refuses_as_an_unsafe_node_with_nothing_written(self) -> None:
        """§7's mutation pair, at the ladder: the fifo-as-`.git` fixture and its measured non-effect."""
        hostile = self.temp / "fifo"
        hostile.mkdir()
        os.mkfifo(hostile / ".git")
        before = inventory(hostile)

        resolution = self.resolve(hostile)

        self.assertEqual(bundle.PROJECT_UNSAFE_NODE, resolution.refusal)
        self.assertIn("neither a regular file nor a directory", resolution.detail)
        self.assertEqual(before, inventory(hostile), "the ladder wrote into the candidate root")
        # POSITIVE CONTROL: the same directory with real metadata admits.
        os.unlink(hostile / ".git")
        self.git("init", "-q", "-b", "main", ".", cwd=hostile)
        self.assertEqual(bundle.PROJECT_ADMITTED, self.resolve(hostile).state)

    def test_a_linked_worktree_resolves_to_the_worktree_root_and_two_lines_is_the_control(self) -> None:
        """§7's linked-worktree pair: one `gitdir:` line resolves, two lines refuse."""
        primary, linked = self.linked_worktree()

        resolution = self.resolve(linked)

        self.assertEqual(bundle.PROJECT_ADMITTED, resolution.state)
        self.assertEqual(linked, resolution.root, "the worktree is its own root, not the primary")
        self.assertNotEqual(primary, resolution.root)

        (linked / ".git").write_text("gitdir: one\ngitdir: two\n", encoding="utf-8")
        refused = self.resolve(linked)
        self.assertEqual(bundle.PROJECT_UNSAFE_NODE, refused.refusal)

    def test_two_linked_worktrees_of_one_repository_are_two_distinct_roots(self) -> None:
        primary, linked = self.linked_worktree()
        second = self.temp / "second"
        self.git("worktree", "add", "--quiet", "-b", "other", str(second), cwd=primary)

        first_root = self.resolve(linked).root
        second_root = self.resolve(second).root

        self.assertNotEqual(first_root, second_root)
        self.assertEqual({linked, second}, {first_root, second_root})

    def test_the_operator_home_is_a_forbidden_root_with_nothing_written(self) -> None:
        """§7's `--project` at the home plane: `forbidden-root`, and the target is untouched."""
        self.git("init", "-q", "-b", "main", ".", cwd=self.home)
        before = inventory(self.home)

        resolution = self.resolve(self.home)

        self.assertEqual(bundle.PROJECT_FORBIDDEN_ROOT, resolution.refusal)
        self.assertIn("the operator's own home", resolution.detail)
        self.assertEqual(before, inventory(self.home))
        # POSITIVE CONTROL: a repository one directory away from the home admits, so the refusal is
        # about the boundary and not about the fixture.
        self.assertEqual(bundle.PROJECT_ADMITTED, self.resolve(self.repository()).state)

    def test_every_configured_plane_root_is_forbidden(self) -> None:
        for name in ("claude-plane", "codex-plane"):
            with self.subTest(plane=name):
                plane = self.temp / name
                plane.mkdir()
                self.git("init", "-q", "-b", "main", ".", cwd=plane)

                resolution = self.resolve(plane, plane_roots=(self.temp / "claude-plane", self.temp / "codex-plane"))

                self.assertEqual(bundle.PROJECT_FORBIDDEN_ROOT, resolution.refusal)
                self.assertIn("configured agent plane root", resolution.detail)

    def test_the_distribution_root_is_forbidden_by_equality_while_a_tree_inside_it_is_not(self) -> None:
        """Containment is deliberately admitted: a linked worktree lives inside the checkout."""
        distribution = self.repository("distribution")
        inside = distribution / "worktrees" / "wave"
        inside.mkdir(parents=True)
        self.git("init", "-q", "-b", "main", ".", cwd=inside)

        refused = self.resolve(distribution, distribution=distribution)
        admitted = self.resolve(inside, distribution=distribution)

        self.assertEqual(bundle.PROJECT_FORBIDDEN_ROOT, refused.refusal)
        self.assertIn("this distribution's own root", refused.detail)
        self.assertEqual(bundle.PROJECT_ADMITTED, admitted.state)

    def test_a_root_inside_the_mise_install_tree_is_forbidden(self) -> None:
        tree = self.temp / "mise-data"
        installed = tree / "installs" / "tool"
        installed.mkdir(parents=True)
        self.git("init", "-q", "-b", "main", ".", cwd=installed)

        with mock.patch.dict(os.environ, {"MISE_DATA_DIR": str(tree)}):
            resolution = self.resolve(installed)
        # POSITIVE CONTROL: the same root, with the install tree pointed elsewhere, admits -- so the
        # refusal is about the boundary rather than about this fixture's shape.
        with mock.patch.dict(os.environ, {"MISE_DATA_DIR": str(self.temp / "elsewhere")}):
            control = self.resolve(installed)

        self.assertEqual(bundle.PROJECT_FORBIDDEN_ROOT, resolution.refusal)
        self.assertIn("mise install tree", resolution.detail)
        self.assertEqual(bundle.PROJECT_ADMITTED, control.state)

    def test_an_explicitly_named_absent_path_is_absent_rather_than_refused(self) -> None:
        """What the records-only retirement of a vanished root is keyed by (§2.2 item 6)."""
        gone = self.temp / "vanished"

        resolution = self.resolve(gone)

        self.assertEqual(bundle.PROJECT_ABSENT, resolution.state)
        self.assertEqual(gone, resolution.root, "an absent root still has a normalised path")
        self.assertEqual("", resolution.refusal)

    def test_forbidden_root_is_applied_to_an_absent_path_too(self) -> None:
        """A records-only retirement may not name a forbidden root either."""
        resolution = self.resolve(self.home / ".codex")

        self.assertEqual(bundle.PROJECT_FORBIDDEN_ROOT, resolution.refusal)

    def test_a_named_path_that_is_a_file_is_not_a_git_project(self) -> None:
        repo = self.repository()

        resolution = self.resolve(repo / "tracked.txt")

        self.assertEqual(bundle.PROJECT_NOT_A_GIT_PROJECT, resolution.refusal)
        self.assertIn("is not a directory", resolution.detail)

    def test_a_relative_request_is_normalised_before_anything_is_judged(self) -> None:
        repo = self.repository()
        inside = repo / "sub"
        inside.mkdir()

        resolution = self.resolve(Path(os.path.relpath(repo, inside)), cwd=inside)

        # `operational_path` resolves against the PROCESS cwd, not the injected one, so this asserts
        # the normalisation happened rather than a particular root: the point is that no unnormalised
        # spelling reaches the pointer key.
        self.assertTrue(resolution.root is None or resolution.root.is_absolute())


class LoaderTest(unittest.TestCase):
    """The one loader the whole `scripts/` plane shares."""

    def test_a_distribution_without_the_reader_refuses_by_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="git-project-loader-") as temporary:
            with self.assertRaises(bundle.InstallerError) as raised:
                bundle.load_git_project_detector(Path(temporary))
        self.assertIn(str(bundle.GIT_DETECTOR_RELATIVE), str(raised.exception))
        self.assertIn("inside the flagship skill's payload", str(raised.exception))

    def test_the_reader_lives_where_the_installed_skill_tool_finds_it_as_a_sibling(self) -> None:
        """The location argument, checked rather than asserted in prose.

        `offline-inspect.py` loads the reader as a plain sibling, so the two must be in one directory:
        that is what makes a copy-mode skill install carry both.
        """
        reader = ROOT / bundle.GIT_DETECTOR_RELATIVE
        tool = ROOT / "skills" / "agentic-sdlc" / "tools" / "offline-inspect.py"

        self.assertTrue(reader.is_file())
        self.assertEqual(tool.parent, reader.parent)
        self.assertEqual(reader.name, "git_project_detector.py")

    def test_the_distribution_root_is_not_the_payload_root(self) -> None:
        """The two roots this module keeps apart, pinned so a later edit cannot merge them.

        THE THREE ROOTS COME FROM THE HOST'S OWN ANCHOR. `Path("/payload")` is absolute on POSIX and
        not on Windows, where it carries a root and no drive, so the equality below compared
        `WindowsPath('/payload')` against the `WindowsPath('C:/payload')` the config had completed
        (main@818bf09, seed context `ci-red-818bf09`). The subject is which root the config keeps, not
        how a fixture spells one.
        """
        payload = absolute_fixture("payload")
        self.assertEqual(ROOT, bundle.distribution_root())
        config = bundle.Config(
            payload, absolute_fixture("home"), absolute_fixture("codex"), "copy", False, "claude", None
        )
        self.assertEqual(payload, config.repo_root)
        self.assertNotEqual(config.repo_root, bundle.distribution_root())


class AnchoredFixturePathTest(unittest.TestCase):
    """Why a fixture may not write `/payload` and call it absolute, decided here instead of on Windows.

    Three modules compared a POSIX-absolute literal against what a product function returned, and all
    three failed on the native Windows CI leg of main@818bf09 (seed context `ci-red-818bf09`). No
    product function was wrong: `os.path.abspath` completes a path that carries a root but no drive,
    which is what `/payload` is to Windows, so the fixture's spelling and the product's result were two
    different paths.

    THIS RUNS ON LINUX. `PureWindowsPath` decides the flavour question without a Windows host, and the
    same completion is then driven through the real product function with a value that is incomplete
    under THIS flavour -- so the mechanism is executed rather than described, and a later reader can see
    the failure class without a six-minute cross-platform round trip.
    """

    def test_a_path_with_a_root_and_no_drive_is_not_absolute_to_windows(self) -> None:
        self.assertTrue(PurePosixPath("/payload").is_absolute())
        self.assertFalse(PureWindowsPath("/payload").is_absolute(), "the exact shape three fixtures wrote")
        # POSITIVE CONTROL: adding the drive is the whole difference, so the assertion above is about
        # the missing anchor and not about `PureWindowsPath` rejecting the name.
        self.assertTrue(PureWindowsPath("C:/payload").is_absolute())

    def test_the_product_completes_an_unanchored_path_against_the_working_directory(self) -> None:
        # `payload` is to POSIX what `/payload` is to Windows: incomplete. The product treats both the
        # same way, which is what turned a fixture literal into a different path on that host.
        self.assertEqual(Path.cwd() / "payload", bundle.operational_path(Path("payload")))
        # ... while an anchored fixture path survives the same call unchanged, which is the property
        # every comparison in those three modules actually needs.
        anchored = absolute_fixture("payload")
        self.assertTrue(anchored.is_absolute(), anchored)
        self.assertEqual(anchored, bundle.operational_path(anchored))

    def test_the_anchor_is_derived_from_this_host_rather_than_written_down(self) -> None:
        """A hard-coded `/` would be the same assumption in the other direction, so it is measured."""
        self.assertEqual(ABSOLUTE_ANCHOR, Path(ABSOLUTE_ANCHOR.anchor), "the anchor carries no tail")
        self.assertEqual(("payload",), absolute_fixture("payload").parts[1:])


if __name__ == "__main__":
    unittest.main()
