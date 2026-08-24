"""Tests for `skills/agentic-sdlc/tools/worktree-custody-preflight.py` (seed `agentic-sdlc-f103`).

Each of the seven named checks gets one refusal test and one positive control, plus the
Decision 9 conformance axes (`docs/plans/decision9-conformance-survey.md`'s own methodology:
`--help`, grammar, supplied-but-missing input, and a real refusal/clear pair) against this one new
surface. Every fixture is a REAL throwaway `git init` repository -- no privilege is required for
six of the seven checks. Only `mount-containment` cannot be exercised with a real second mount from
an unprivileged CI host, so its tests import the tool directly via
`importlib.util.spec_from_file_location` (its hyphenated filename means a plain `import` cannot
name it) and monkeypatch its own `_mount_id_fd` seam in-process -- the technique the retired
activation-transaction tests used for the primitive this tool re-expresses.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "worktree-custody-preflight.py"

_spec = importlib.util.spec_from_file_location("worktree_custody_preflight", TOOL)
assert _spec is not None and _spec.loader is not None
wcp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = wcp
_spec.loader.exec_module(wcp)

def _mount_ids_answerable() -> bool:
    """Whether THIS host answers statx mount IDs, asked through the tool's OWN seam.

    A CAPABILITY probe, not a platform sniff: `_mount_id_fd` is exactly what every real
    preflight run consults, so if a non-Linux host ever grows an answer this returns True and
    the skips below stop firing. Where the host cannot answer, the product refuses
    mount-containment BY NAME (`this host cannot verify mount containment`) on every real run,
    so no unpatched run can reach a `clear` disposition or an `unevaluated` mount verdict.
    """
    try:
        fd = os.open(os.getcwd(), os.O_RDONLY)
    except OSError:
        return False
    try:
        wcp._mount_id_fd(fd)
        return True
    except wcp.MountUnsupported:
        return False
    finally:
        os.close(fd)


MOUNT_IDS_ANSWERABLE = _mount_ids_answerable()
MOUNT_IDS_SKIP_REASON = (
    "this host does not answer statx mount IDs, so mount-containment refuses by name on every "
    "unpatched run and no real preflight can reach the verdict this test asserts"
)

#: An ALLOWLIST, not an inheritance -- mirrors the retired planning-snapshot tests' own
#: `PASSTHROUGH_ENV`/`constructed_environment`, re-expressed rather than imported per this
#: repository's own cross-test-module convention.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    if extra:
        environment.update(extra)
    return environment


def git(*args: str) -> None:
    subprocess.run(["git", *args], check=True, capture_output=True, env=constructed_environment())


def make_repo(root: Path) -> Path:
    """One throwaway git repository with a single commit, real `git`, no mocking."""
    repo = root / "repo"
    repo.mkdir()
    git("init", "-q", str(repo))
    git("-C", str(repo), "config", "user.email", "test@example.com")
    git("-C", str(repo), "config", "user.name", "test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    git("-C", str(repo), "add", "README.md")
    git("-C", str(repo), "commit", "-q", "-m", "init")
    return repo


def run(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-B", str(TOOL), *args],
        capture_output=True,
        env=constructed_environment(),
        check=False,
    )


def parse(completed: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    return json.loads(completed.stdout.decode("utf-8"))


def statuses(result: dict[str, Any]) -> dict[str, str]:
    return {entry["slug"]: entry["status"] for entry in result["checks"]}


def reasons(result: dict[str, Any]) -> dict[str, str | None]:
    return {entry["slug"]: entry["reason"] for entry in result["checks"]}


@unittest.skipIf(
    os.name == "nt",
    "the wave chain that runs this preflight is Linux doctrine (statx mount-id containment); "
    "these git fixtures are unproven on native Windows",
)
class RepoCase(unittest.TestCase):
    """One fresh throwaway repository per test method."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = make_repo(Path(self._tmp.name))

    def check(self, custody: str) -> tuple[dict[str, Any], int]:
        completed = run("--target", str(self.repo), "--custody", custody)
        return parse(completed), completed.returncode


# ---- Decision 9 conformance: the survey's own four axes, against this one new surface -------------


class DecisionNineTests(RepoCase):
    def test_exit_constants_are_the_documented_subset(self) -> None:
        self.assertEqual((wcp.EXIT_OK, wcp.EXIT_INTERNAL, wcp.EXIT_INPUT, wcp.EXIT_REFUSED), (0, 1, 2, 3))

    def test_help_exits_zero(self) -> None:
        completed = run("--help")
        self.assertEqual(completed.returncode, 0)
        self.assertIn(b"Exit codes", completed.stdout)

    def test_no_arguments_is_a_grammar_error(self) -> None:
        completed = run()
        self.assertEqual(completed.returncode, wcp.EXIT_INPUT)
        self.assertIn(b"required", completed.stderr)
        self.assertEqual(completed.stdout, b"")

    def test_an_unknown_flag_is_a_grammar_error(self) -> None:
        completed = run("--zzz-not-a-flag")
        self.assertEqual(completed.returncode, wcp.EXIT_INPUT)

    def test_a_supplied_but_missing_target_is_exit_two_not_a_traceback(self) -> None:
        missing = self.repo / "nope"
        completed = run("--target", str(missing), "--custody", ".worktrees/x")
        self.assertEqual(completed.returncode, wcp.EXIT_INPUT)
        self.assertIn(b"does not exist", completed.stderr)
        # No result document at all: the question could not be asked, so nothing was derived --
        # distinct from a NAMED REFUSAL, which always seals a result on stdout.
        self.assertEqual(completed.stdout, b"")

    def test_a_relative_target_is_exit_two(self) -> None:
        completed = run("--target", "relative/path", "--custody", ".worktrees/x")
        self.assertEqual(completed.returncode, wcp.EXIT_INPUT)
        self.assertIn(b"absolute", completed.stderr)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_a_clear_run_exits_zero(self) -> None:
        result, code = self.check(".worktrees/seed-slug")
        self.assertEqual(code, wcp.EXIT_OK)
        self.assertEqual(result["disposition"], "clear")

    def test_a_refused_run_exits_three(self) -> None:
        result, code = self.check("../outside")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(result["disposition"], "refused")


class ResultShapeTests(RepoCase):
    def test_all_seven_slugs_are_always_present_in_fixed_order(self) -> None:
        result, _ = self.check("../outside")
        self.assertEqual([entry["slug"] for entry in result["checks"]], list(wcp.CHECK_SLUGS))
        self.assertEqual(len(wcp.CHECK_SLUGS), 7)

    def test_a_control_character_in_a_refused_custody_value_is_escaped_not_injected(self) -> None:
        custody = "../elsewhere\x07\x1b[31mFAKE\x1b[0m"
        completed = run("--target", str(self.repo), "--custody", custody)
        self.assertNotIn(b"\x07", completed.stdout)
        self.assertNotIn(b"\x1b", completed.stdout)
        result = parse(completed)
        self.assertIn("\\x07", reasons(result)["custody-spelling"])


# ---- custody-spelling ------------------------------------------------------------------------------


class CustodySpellingTests(RepoCase):
    def test_a_dot_dot_segment_is_refused(self) -> None:
        result, code = self.check(".worktrees/../elsewhere")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-spelling"], wcp.REFUSED)

    def test_a_backslash_is_refused(self) -> None:
        result, code = self.check(".worktrees\\evil")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-spelling"], wcp.REFUSED)
        self.assertIn("backslash", reasons(result)["custody-spelling"])

    def test_a_nul_byte_is_refused_via_direct_main_argv(self) -> None:
        """A NUL cannot survive `execve`'s argv, so a real second process can never carry one in
        `--custody`; this goes straight through `main()` in this same process instead of a
        subprocess/shell round trip, exactly as the task that pinned this test requires.
        """
        custody = ".worktrees/evil\x00tail"

        class _FakeStdout:
            def __init__(self) -> None:
                self.buffer = io.BytesIO()

        fake_stdout = _FakeStdout()
        original_stdout = wcp.sys.stdout
        wcp.sys.stdout = fake_stdout
        try:
            exit_code = wcp.main(["--target", str(self.repo), "--custody", custody])
        finally:
            wcp.sys.stdout = original_stdout

        result = json.loads(fake_stdout.buffer.getvalue().decode("utf-8"))
        self.assertEqual(exit_code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-spelling"], wcp.REFUSED)
        self.assertIn("NUL", reasons(result)["custody-spelling"])

    def test_an_absolute_custody_is_refused(self) -> None:
        result, code = self.check("/tmp/somewhere")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-spelling"], wcp.REFUSED)

    def test_an_empty_custody_is_a_named_refusal_not_a_grammar_error(self) -> None:
        """Supplied-but-empty is a business-rule refusal (3), never a grammar error (2)."""
        result, code = self.check("")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-spelling"], wcp.REFUSED)

    def test_positive_control_a_well_spelled_custody_passes_spelling(self) -> None:
        result, _ = self.check(".worktrees/seed-slug")
        self.assertEqual(statuses(result)["custody-spelling"], wcp.MET)

    def test_gating_every_later_check_is_unevaluated_not_met(self) -> None:
        result, _ = self.check("../elsewhere")
        later = statuses(result)
        for slug in wcp.CHECK_SLUGS[1:]:
            self.assertEqual(later[slug], wcp.UNEVALUATED, slug)
            self.assertIsNotNone(reasons(result)[slug])


# ---- custody-root -----------------------------------------------------------------------------


class CustodyRootTests(RepoCase):
    def test_a_path_outside_worktrees_is_refused(self) -> None:
        result, code = self.check("other/thing")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-root"], wcp.REFUSED)
        # The earlier check is unaffected: this is a distinct, independently testable dimension.
        self.assertEqual(statuses(result)["custody-spelling"], wcp.MET)

    def test_worktrees_itself_with_no_child_is_refused(self) -> None:
        result, code = self.check(".worktrees")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["custody-root"], wcp.REFUSED)

    def test_positive_control_a_child_of_worktrees_passes_root(self) -> None:
        result, _ = self.check(".worktrees/seed-slug")
        self.assertEqual(statuses(result)["custody-root"], wcp.MET)

    def test_gating_later_checks_are_unevaluated(self) -> None:
        result, _ = self.check("other/thing")
        later = statuses(result)
        for slug in wcp.CHECK_SLUGS[2:]:
            self.assertEqual(later[slug], wcp.UNEVALUATED, slug)


# ---- path-integrity ---------------------------------------------------------------------------


class PathIntegrityTests(RepoCase):
    def setUp(self) -> None:
        super().setUp()
        (self.repo / ".worktrees").mkdir()

    def test_a_symlink_component_is_refused(self) -> None:
        os.symlink("/tmp", self.repo / ".worktrees" / "evil")
        result, code = self.check(".worktrees/evil/child")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["path-integrity"], wcp.REFUSED)
        self.assertIn("symlink", reasons(result)["path-integrity"])

    def test_a_special_node_component_is_refused(self) -> None:
        (self.repo / ".worktrees" / "plain-file").write_text("not a directory\n", encoding="utf-8")
        result, code = self.check(".worktrees/plain-file/child")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["path-integrity"], wcp.REFUSED)
        self.assertIn("not a directory", reasons(result)["path-integrity"])

    def test_positive_control_a_not_yet_created_destination_passes_path_integrity(self) -> None:
        result, _ = self.check(".worktrees/brand-new-slug")
        self.assertEqual(statuses(result)["path-integrity"], wcp.MET)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_positive_control_a_preexisting_empty_directory_passes_path_integrity(self) -> None:
        # `references/worktree-lifecycle.md`'s verified fact 5: `git worktree add` tolerates an
        # existing EMPTY directory. This preflight must not refuse the case Git itself accepts.
        (self.repo / ".worktrees" / "empty-dir").mkdir()
        result, code = self.check(".worktrees/empty-dir")
        self.assertEqual(statuses(result)["path-integrity"], wcp.MET)
        self.assertEqual(result["disposition"], "clear")
        self.assertEqual(code, wcp.EXIT_OK)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_gating_registration_checks_are_unevaluated_after_a_symlink_refusal(self) -> None:
        os.symlink("/tmp", self.repo / ".worktrees" / "evil2")
        result, _ = self.check(".worktrees/evil2/child")
        later = statuses(result)
        self.assertEqual(later["registration-occupied"], wcp.UNEVALUATED)
        self.assertEqual(later["registration-drifted"], wcp.UNEVALUATED)
        self.assertEqual(later["mount-containment"], wcp.UNEVALUATED)


# ---- destination-vacancy -----------------------------------------------------------------------


class DestinationVacancyTests(RepoCase):
    def setUp(self) -> None:
        super().setUp()
        (self.repo / ".worktrees").mkdir()

    def test_an_occupied_destination_holding_even_one_dotfile_is_refused(self) -> None:
        occupied = self.repo / ".worktrees" / "occupied"
        occupied.mkdir()
        # A bare dotfile is deliberately the only entry: `git worktree add` still refuses a
        # directory holding nothing but a dotfile, so this preflight must not treat it as empty.
        (occupied / ".gitkeep").write_text("", encoding="utf-8")
        result, code = self.check(".worktrees/occupied")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["destination-vacancy"], wcp.REFUSED)
        self.assertIn("not empty", reasons(result)["destination-vacancy"])
        self.assertIn(".gitkeep", reasons(result)["destination-vacancy"])

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_positive_control_a_preexisting_empty_directory_is_vacant(self) -> None:
        empty = self.repo / ".worktrees" / "empty"
        empty.mkdir()
        result, code = self.check(".worktrees/empty")
        self.assertEqual(statuses(result)["destination-vacancy"], wcp.MET)
        self.assertEqual(result["disposition"], "clear")
        self.assertEqual(code, wcp.EXIT_OK)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_positive_control_an_absent_destination_is_vacant(self) -> None:
        result, code = self.check(".worktrees/never-created")
        self.assertEqual(statuses(result)["destination-vacancy"], wcp.MET)
        self.assertEqual(result["disposition"], "clear")
        self.assertEqual(code, wcp.EXIT_OK)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_a_real_git_worktree_add_succeeds_after_a_clear_verdict_with_no_stranded_branch(
        self,
    ) -> None:
        """The executable proof this family's own docs cite: the exact custody a clear verdict
        names is one `git worktree add` accepts outright, and the branch it creates backs a real
        worktree rather than being stranded by a refusal this preflight already ruled out."""
        result, code = self.check(".worktrees/real-add")
        self.assertEqual(result["disposition"], "clear")
        self.assertEqual(code, wcp.EXIT_OK)

        branch = "work/real-add"
        target = self.repo / ".worktrees" / "real-add"
        added = subprocess.run(
            ["git", "-C", str(self.repo), "worktree", "add", str(target), "-b", branch],
            capture_output=True,
            env=constructed_environment(),
            check=False,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertTrue(target.is_dir())

        listing = subprocess.run(
            ["git", "-C", str(self.repo), "worktree", "list", "--porcelain", "-z"],
            capture_output=True,
            env=constructed_environment(),
            check=False,
        )
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn(str(target), listing.stdout.decode("utf-8"))
        branches = subprocess.run(
            ["git", "-C", str(self.repo), "branch", "--list", branch],
            capture_output=True,
            env=constructed_environment(),
            check=False,
        )
        self.assertIn(branch, branches.stdout.decode("utf-8"))


# ---- mount-containment: the tool's own monkeypatchable seam, in-process ---------------------------


class MountContainmentTests(RepoCase):
    """No unprivileged CI host can bind-mount a second real filesystem under a throwaway fixture
    repository, so this calls `run_preflight` directly and monkeypatches `_mount_id_fd` -- the same
    technique the retired activation-transaction tests' own foreign-mount refusal used for the
    primitive this tool re-expresses.
    """

    def setUp(self) -> None:
        super().setUp()
        (self.repo / ".worktrees").mkdir()

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_a_component_on_a_foreign_mount_is_refused(self) -> None:
        original = wcp._mount_id_fd
        calls = {"n": 0}

        def fake(fd: int) -> int:
            calls["n"] += 1
            value = original(fd)
            # The FIRST call captures the target root's own identity with the REAL value; only
            # calls after that are perturbed, so a genuinely same-mount root can never trip this on
            # its own -- proof that the refusal below is this seam, not a coincidence.
            return value if calls["n"] == 1 else value + 1

        wcp._mount_id_fd = fake
        try:
            result = wcp.run_preflight(self.repo, ".worktrees/mnt-child")
        finally:
            wcp._mount_id_fd = original
        self.assertGreater(calls["n"], 1)
        found = {entry["slug"]: entry for entry in result["checks"]}
        self.assertEqual(found["mount-containment"]["status"], wcp.REFUSED)
        self.assertIn("mount boundary", found["mount-containment"]["reason"])
        self.assertEqual(result["disposition"], "refused")

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_positive_control_the_unpatched_seam_reports_met(self) -> None:
        result = wcp.run_preflight(self.repo, ".worktrees/mnt-child")
        found = {entry["slug"]: entry["status"] for entry in result["checks"]}
        self.assertEqual(found["mount-containment"], wcp.MET)
        self.assertEqual(result["disposition"], "clear")

    def test_an_unsupported_host_refuses_rather_than_silently_passing(self) -> None:
        """`checks consult recorded unknowns`: an inconclusive mount question is a refusal, not a
        default `met`."""
        original = wcp._mount_id_fd

        def unsupported(fd: int) -> int:
            raise wcp.MountUnsupported("simulated for this test")

        wcp._mount_id_fd = unsupported
        try:
            result = wcp.run_preflight(self.repo, ".worktrees/mnt-child")
        finally:
            wcp._mount_id_fd = original
        found = {entry["slug"]: entry for entry in result["checks"]}
        self.assertEqual(found["mount-containment"]["status"], wcp.REFUSED)
        self.assertIn("cannot verify", found["mount-containment"]["reason"])
        # path-integrity does not depend on statx at all, and must still be decided.
        self.assertEqual(found["path-integrity"]["status"], wcp.MET)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_an_unanswerable_child_mount_id_is_refused_by_name_not_silently_passed(self) -> None:
        """Distinct from the ROOT-unanswerable case above: here the ROOT answers normally (so
        `mount_supported` is True and the walk actually reaches a child's own statx call), and
        only a CHILD's mount id is unanswerable. The prior shape of this branch fell back to
        `child_mount = None` and skipped the comparison, which let an unanswerable component pass
        mount-containment outright -- exactly the silent-pass defect this check exists to avoid.
        """
        # The destination must already EXIST as a real directory: a not-yet-created segment
        # short-circuits the walk on `FileNotFoundError` (vacancy is decided and the loop breaks)
        # before its own mount check ever runs, so the child's `_mount_id_fd` call this test
        # depends on would never happen against an absent destination.
        (self.repo / ".worktrees" / "mnt-child").mkdir()

        original = wcp._mount_id_fd
        calls = {"n": 0}

        def fake(fd: int) -> int:
            calls["n"] += 1
            if calls["n"] <= 2:
                # Call 1 is the target root's own identity capture in `_open_target_root` (must
                # stay answerable, or `mount_supported` would be False and this would exercise the
                # already-covered root-unanswerable branch). Call 2 is the FIRST custody segment
                # (`.worktrees`, pre-created by `setUp`) -- also left answerable, so the refusal
                # below is provably about the LAST segment (`mnt-child`), not an earlier one.
                return original(fd)
            raise wcp.MountUnsupported("simulated for this test: this one child is unanswerable")

        wcp._mount_id_fd = fake
        try:
            result = wcp.run_preflight(self.repo, ".worktrees/mnt-child")
        finally:
            wcp._mount_id_fd = original
        self.assertEqual(calls["n"], 3)
        found = {entry["slug"]: entry for entry in result["checks"]}
        self.assertEqual(found["mount-containment"]["status"], wcp.REFUSED)
        self.assertIn("mnt-child", found["mount-containment"]["reason"])
        self.assertIn("cannot be checked for mount containment", found["mount-containment"]["reason"])
        self.assertEqual(result["disposition"], "refused")
        # destination-vacancy is a DIFFERENT question and is still correctly MET: the directory
        # exists and is empty, so this refusal is provably about mount containment alone.
        self.assertEqual(found["destination-vacancy"]["status"], wcp.MET)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_a_dev_mismatch_alone_is_refused_even_when_the_mount_id_is_unpatched(self) -> None:
        """Pins the containment comparison to BOTH `st_dev` and the mount id: a mutant that
        dropped `st_dev` from the `(child_dev, child_mount) != (...)` tuple and compared only the
        mount id would let this pass, since `_mount_id_fd` is left completely untouched here --
        only `os.fstat`'s reported `st_dev` is perturbed for the custody walk's own calls.
        """
        original_fstat = wcp.os.fstat
        calls = {"n": 0}

        class _FakeStat:
            def __init__(self, st_dev: int) -> None:
                self.st_dev = st_dev

        def fake(fd, *args, **kwargs):
            calls["n"] += 1
            real = original_fstat(fd, *args, **kwargs)
            if calls["n"] == 1:
                # The root's own identity capture in `_open_target_root` must stay real, or this
                # test would be comparing a perturbed root against itself and prove nothing.
                return real
            return _FakeStat(real.st_dev + 1)

        wcp.os.fstat = fake
        try:
            result = wcp.run_preflight(self.repo, ".worktrees/dev-child")
        finally:
            wcp.os.fstat = original_fstat
        self.assertGreater(calls["n"], 1)
        found = {entry["slug"]: entry for entry in result["checks"]}
        self.assertEqual(found["mount-containment"]["status"], wcp.REFUSED)
        self.assertIn("mount boundary", found["mount-containment"]["reason"])
        self.assertEqual(result["disposition"], "refused")


# ---- registration-occupied ---------------------------------------------------------------------


class RegistrationOccupiedTests(RepoCase):
    def test_an_active_worktree_registration_is_refused(self) -> None:
        wt = self.repo / ".worktrees" / "occ"
        git("-C", str(self.repo), "worktree", "add", "-q", str(wt), "-b", "br-occ")
        result, code = self.check(".worktrees/occ")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["registration-occupied"], wcp.REFUSED)
        self.assertIn("already registered as an active", reasons(result)["registration-occupied"])
        # The companion check is a DIFFERENT question and must not be conflated with this one.
        self.assertEqual(statuses(result)["registration-drifted"], wcp.MET)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_positive_control_an_unregistered_path_passes(self) -> None:
        result, code = self.check(".worktrees/never-registered")
        self.assertEqual(statuses(result)["registration-occupied"], wcp.MET)
        self.assertEqual(result["disposition"], "clear")
        self.assertEqual(code, wcp.EXIT_OK)


# ---- registration-drifted ----------------------------------------------------------------------


class RegistrationDriftedTests(RepoCase):
    def test_a_drifted_registration_is_refused(self) -> None:
        wt = self.repo / ".worktrees" / "drift"
        git("-C", str(self.repo), "worktree", "add", "-q", str(wt), "-b", "br-drift")
        shutil.rmtree(wt)
        result, code = self.check(".worktrees/drift")
        self.assertEqual(code, wcp.EXIT_REFUSED)
        self.assertEqual(statuses(result)["registration-drifted"], wcp.REFUSED)
        self.assertIn("no longer exists", reasons(result)["registration-drifted"])
        self.assertIn("prune", reasons(result)["registration-drifted"])
        # The companion check is a DIFFERENT question: the directory is gone, so it is not "active".
        self.assertEqual(statuses(result)["registration-occupied"], wcp.MET)

    @unittest.skipUnless(MOUNT_IDS_ANSWERABLE, MOUNT_IDS_SKIP_REASON)
    def test_positive_control_a_pruned_registration_passes(self) -> None:
        wt = self.repo / ".worktrees" / "pruned"
        git("-C", str(self.repo), "worktree", "add", "-q", str(wt), "-b", "br-pruned")
        shutil.rmtree(wt)
        git("-C", str(self.repo), "worktree", "prune")
        result, code = self.check(".worktrees/pruned")
        self.assertEqual(statuses(result)["registration-drifted"], wcp.MET)
        self.assertEqual(result["disposition"], "clear")
        self.assertEqual(code, wcp.EXIT_OK)


class OffLinuxImportTests(unittest.TestCase):
    """The module must import off-Linux so `_mount_id_fd`'s named refusal can actually fire.

    Windows CI proved the inverse: a module-scope `ctypes.CDLL(None)` raised TypeError at import,
    every custody test collapsed into one loader error, and the MountUnsupported refusal was dead
    code. The probe stubs CDLL to fail loudly, so the guard — not a permissive loader — is what
    the pass proves.
    """

    def test_off_linux_import_keeps_the_named_refusal_alive(self) -> None:
        from unittest import mock

        spec = importlib.util.spec_from_file_location("wcp_off_linux_probe", TOOL)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "platform", "win32"), mock.patch(
            "ctypes.CDLL", side_effect=AssertionError("CDLL must not be bound off-Linux")
        ):
            spec.loader.exec_module(module)
            with self.assertRaises(module.MountUnsupported):
                module._mount_id_fd(0)

    def test_positive_control_the_linux_import_binds_statx(self) -> None:
        if sys.platform != "linux":
            self.skipTest("the statx binding exists only on Linux")
        self.assertIsNotNone(wcp._LIBC_STATX)


if __name__ == "__main__":
    unittest.main()
