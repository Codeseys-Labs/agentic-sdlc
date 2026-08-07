from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "skills" / "agentic-sdlc" / "references" / "worktree-failclosed-tests.md"
RECIPE = ROOT / "commands" / "sdlc-wave.md"
SUBSTRATE = ROOT / "skills" / "agentic-sdlc" / "references" / "seeds-worktrees.md"
LIFECYCLE = ROOT / "skills" / "agentic-sdlc" / "references" / "worktree-lifecycle.md"
# The documented in-workspace substrate directory, gitignored end to end.
WORKTREE_DIRECTORY = ".worktrees"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run git against `repo` with an isolated, deterministic environment.

    Mirrors tests/test_prime_candidate_custody.py's git() helper: strip every
    GIT_* environment variable (this test process may itself be executing
    inside a worktree of the protected agentic-sdlc repo, so ambient GIT_DIR /
    GIT_WORK_TREE / etc. must never leak into the throwaway fixture) and pin
    identity via -c flags rather than writing a real ~/.gitconfig or a repo
    config entry.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(
        [
            "git",
            "-c", "user.name=fixture",
            "-c", "user.email=fixture@example.invalid",
            "-C", str(repo),
            *args,
        ],
        cwd=repo,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
    )


def worktree_list(repo: Path) -> str:
    return git(repo, "worktree", "list", "--porcelain").stdout


def branch_list(repo: Path) -> str:
    return git(repo, "branch", "--list", "--format=%(refname)").stdout


def init_fixture(repo: Path) -> None:
    git(repo, "init", "-q", "-b", "main")
    (repo / "seed.txt").write_text("seed\n")
    # The documented substrate: the worktree directory is INSIDE the workspace and
    # gitignored end to end (skills/agentic-sdlc/references/seeds-worktrees.md
    # "Worktree substrate"), so the fixture must carry the ignore rule too.
    (repo / ".gitignore").write_text(f"{WORKTREE_DIRECTORY}/\n")
    git(repo, "add", "seed.txt", ".gitignore")
    git(repo, "commit", "-q", "-m", "seed")


class WorktreeFailClosedTests(unittest.TestCase):
    """Pure-git fail-closed cases for the commands/sdlc-wave.md worktree recipe.

    commands/sdlc-wave.md step 3 pins the exact recipe under test:
        git -C <repo> worktree add <repo>/.worktrees/<seed-id>-<slug> \
            -b work/<seed-id>-<slug> <base>
    This repo bundles no dispatcher, so each case below issues that literal
    git invocation against a disposable fixture repo built fresh under
    tempfile.TemporaryDirectory (never this checkout), and checks whether the
    raw command leaves the fixture's worktree/branch state byte-identical to
    its pre-attempt state after a refusal, per the fail-closed contract in
    skills/agentic-sdlc/references/worktree-failclosed-tests.md.

    Every target path is <fixture-repo>/.worktrees/<id>, matching the
    in-workspace substrate rather than a sibling directory, so a Git release
    that stopped supporting `worktree add` under a gitignored path would fail
    these cases instead of silently invalidating the documented lifecycle.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "fixture-repo"
        self.repo.mkdir()
        init_fixture(self.repo)

    def worktree(self, identifier: str) -> Path:
        """Return the in-workspace target path for `identifier`."""
        return self.repo / WORKTREE_DIRECTORY / identifier

    def test_a_occupied_branch_refuses_and_leaves_no_orphan(self) -> None:
        """Executes worktree-failclosed-tests.md Failure-mode catalog #1 (Occupied isolation branch)."""
        branch = "work/s1-x"
        first = self.worktree("s1-x-first")
        second = self.worktree("s1-x-second")
        git(self.repo, "worktree", "add", str(first), "-b", branch)

        before_worktrees = worktree_list(self.repo)
        before_branches = branch_list(self.repo)

        result = git(self.repo, "worktree", "add", str(second), "-b", branch, check=False)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(second.exists())
        self.assertEqual(worktree_list(self.repo), before_worktrees)
        self.assertEqual(branch_list(self.repo), before_branches)

    def test_b_occupied_target_path_strands_a_branch_and_the_guarded_recipe_recovers(self) -> None:
        """Executes worktree-failclosed-tests.md general-shape guarantee #5 (no orphaned worktree/branch artifact) for the occupied-path precondition.

        The raw git command cannot deliver the guarantee here: git creates the
        named branch before checking whether the target path is free, so a
        refusal strands an orphan branch. This test pins that fail-open
        behavior (if a future git fixes it, this fails and the runbook guard
        in commands/sdlc-wave.md can be relaxed) and then proves the runbook's
        documented recovery restores byte-identical fail-closed state.
        """
        branch = "work/s2-y"
        target = self.worktree("s2-y")
        target.mkdir(parents=True)
        (target / "preexisting.txt").write_text("occupies the target path\n")

        before_worktrees = worktree_list(self.repo)
        before_branches = branch_list(self.repo)

        result = git(self.repo, "worktree", "add", str(target), "-b", branch, check=False)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(worktree_list(self.repo), before_worktrees)
        self.assertEqual(list(target.iterdir()), [target / "preexisting.txt"])
        # The pinned hazard: the refusal leaves the isolation branch behind.
        self.assertIn(f"refs/heads/{branch}", branch_list(self.repo))
        # The runbook recovery: delete the stranded branch, then require the
        # repository to be byte-identical to its pre-attempt state.
        git(self.repo, "branch", "-d", branch)
        self.assertEqual(worktree_list(self.repo), before_worktrees)
        self.assertEqual(branch_list(self.repo), before_branches)

    def test_c_dirty_index_does_not_leak_into_new_worktree(self) -> None:
        """Executes worktree-failclosed-tests.md Control cases: "Satisfiable isolation still runs" (assert the dispatched directory positively matches the branch point, not merely "not equal to the shared checkout"), extended to prove the caller's dirty index/worktree is not part of what gets dispatched."""
        branch = "work/s3-z"
        target = self.worktree("s3-z")

        (self.repo / "seed.txt").write_text("seed\nstaged dirt\n")
        git(self.repo, "add", "seed.txt")
        (self.repo / "seed.txt").write_text("seed\nstaged dirt\nunstaged dirt\n")
        (self.repo / "untracked.txt").write_text("never committed\n")

        result = git(self.repo, "worktree", "add", str(target), "-b", branch, check=False)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((target / "seed.txt").read_text(), "seed\n")
        self.assertFalse((target / "untracked.txt").exists())
        self.assertEqual(git(target, "status", "--porcelain").stdout, "")
        # The dirty state in the original checkout is untouched by the isolated add.
        self.assertEqual((self.repo / "seed.txt").read_text(), "seed\nstaged dirt\nunstaged dirt\n")
        self.assertTrue((self.repo / "untracked.txt").exists())

    def test_d_in_workspace_worktree_stays_invisible_to_the_workspace(self) -> None:
        """Executes worktree-lifecycle.md Verified Git fact 1: `worktree add` succeeds under a
        gitignored path and the main workspace's status stays clean, so `.worktrees/` never
        enters a commit. Falsifiability: the same add into an UNIGNORED directory shows up as
        untracked and `git add -A` stages it as an embedded repository (a gitlink), which is
        the concrete failure the ignore rule prevents."""
        target = self.worktree("s4-ignored")
        result = git(self.repo, "worktree", "add", str(target), "-b", "work/s4-ignored", check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain", "--untracked-files=all").stdout, "")
        # Fact 2: a linked worktree's git-dir differs from the common git-dir; that inequality
        # is the portable "am I in a linked worktree" test the record seam depends on.
        self.assertNotEqual(
            git(target, "rev-parse", "--absolute-git-dir").stdout,
            git(target, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout,
        )
        self.assertEqual(
            git(self.repo, "rev-parse", "--absolute-git-dir").stdout,
            git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout,
        )
        # Falsifiable control: without the ignore rule the same layout pollutes the index.
        unignored = Path(self.tmp.name) / "unignored-repo"
        unignored.mkdir()
        git(unignored, "init", "-q", "-b", "main")
        (unignored / "seed.txt").write_text("seed\n")
        git(unignored, "add", "seed.txt")
        git(unignored, "commit", "-q", "-m", "seed")
        git(unignored, "worktree", "add", str(unignored / WORKTREE_DIRECTORY / "s4"), "-b", "work/s4")
        self.assertIn(WORKTREE_DIRECTORY, git(unignored, "status", "--porcelain").stdout)
        git(unignored, "add", "-A")
        self.assertIn(
            f"{WORKTREE_DIRECTORY}/s4",
            git(unignored, "ls-files", "--stage").stdout,
        )

    def test_e_manual_removal_needs_prune_before_the_path_is_reusable(self) -> None:
        """Executes worktree-lifecycle.md Verified Git fact 8 and the Step 6 "someone deleted
        the directory with rm -rf" recovery row: a manual delete leaves a prunable
        registration that blocks re-adding the same path until `worktree prune` clears it, and
        prune touches the registration only — never the branch."""
        target = self.worktree("s5-stale")
        branch = "work/s5-stale"
        git(self.repo, "worktree", "add", str(target), "-b", branch)
        shutil.rmtree(target)

        self.assertIn("prunable", worktree_list(self.repo))
        blocked = git(self.repo, "worktree", "add", str(target), branch, check=False)
        self.assertNotEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
        self.assertIn("already registered", blocked.stdout + blocked.stderr)

        git(self.repo, "worktree", "prune")
        self.assertNotIn("prunable", worktree_list(self.repo))
        # Prune is registration-only: the branch survives and the path is reusable.
        self.assertIn(f"refs/heads/{branch}", branch_list(self.repo))
        reused = git(self.repo, "worktree", "add", str(target), branch, check=False)
        self.assertEqual(reused.returncode, 0, reused.stdout + reused.stderr)

    def test_f_cleanup_refuses_dirty_removal_and_squash_landed_branch_deletion(self) -> None:
        """Executes worktree-lifecycle.md Step 6's two cleanup refusals: `worktree remove`
        refuses a worktree holding untracked content (so `--force` on an uninspected tree is
        silent work loss), and a squash-landed branch still fails `branch -d` because a squash
        creates no merge edge — the content-equivalence diff is the check that reflects
        reality (Verified Git fact 9)."""
        target = self.worktree("s6-land")
        branch = "work/s6-land"
        git(self.repo, "worktree", "add", str(target), "-b", branch)
        (target / "landed.txt").write_text("real work\n")
        git(target, "add", "landed.txt")
        git(target, "commit", "-q", "-m", "worker commit")

        git(self.repo, "merge", "--squash", branch)
        git(self.repo, "commit", "-q", "-m", "squash: worker commit")
        # Content landed, but the squash left no merge edge for -d to observe.
        self.assertEqual(git(self.repo, "diff", "--stat", "main", branch).stdout, "")
        self.assertNotIn(f"refs/heads/{branch}", git(self.repo, "branch", "--merged", "main", "--format=%(refname)").stdout)

        # Untracked debris blocks removal; the branch is still checked out, so -d refuses too.
        (target / "gate-debris.txt").write_text("planted by a gate run\n")
        dirty = git(self.repo, "worktree", "remove", str(target), check=False)
        self.assertNotEqual(dirty.returncode, 0, dirty.stdout + dirty.stderr)
        self.assertTrue(target.exists())
        checked_out = git(self.repo, "branch", "-d", branch, check=False)
        self.assertNotEqual(checked_out.returncode, 0, checked_out.stdout + checked_out.stderr)

        # The documented order: inspect, force-remove, then -D on the verified-landed branch.
        self.assertIn("gate-debris.txt", git(target, "status", "--porcelain").stdout)
        git(self.repo, "worktree", "remove", "--force", str(target))
        unmerged = git(self.repo, "branch", "-d", branch, check=False)
        self.assertNotEqual(unmerged.returncode, 0, unmerged.stdout + unmerged.stderr)
        git(self.repo, "branch", "-D", branch)
        self.assertEqual(branch_list(self.repo), "refs/heads/main\n")

    def test_g_substrate_is_documented_in_workspace_with_one_owner(self) -> None:
        """The prose under test names the in-workspace substrate and keeps one owner for it:
        seeds-worktrees.md carries the canonical rule, the lifecycle reference and the wave
        runbook point at it, and no shipped surface still prescribes a sibling worktree."""
        substrate = SUBSTRATE.read_text(encoding="utf-8")
        lifecycle = LIFECYCLE.read_text(encoding="utf-8")
        recipe = RECIPE.read_text(encoding="utf-8")

        self.assertIn(f"<repo>/{WORKTREE_DIRECTORY}/<seed-id>-<slug>/", substrate)
        self.assertIn("Canonical rule, owned here", substrate)
        self.assertIn("references/worktree-lifecycle.md", substrate)
        self.assertIn("references/seeds-worktrees.md", lifecycle)
        self.assertIn(f"{WORKTREE_DIRECTORY}/<seed-id>-<slug>", recipe)
        self.assertIn("references/worktree-lifecycle.md", recipe)
        # Every documented lifecycle step carries a refusal/recovery case.
        for step in ("create", "gate", "review", "integrate", "reconcile", "clean up"):
            with self.subTest(step=step):
                self.assertIn(step, lifecycle.lower())
        for path in (substrate, lifecycle, recipe, SPEC.read_text(encoding="utf-8")):
            self.assertNotRegex(path, r"worktree add\s+\.\./")


if __name__ == "__main__":
    unittest.main()
