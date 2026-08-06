from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "skills" / "agentic-sdlc" / "references" / "worktree-failclosed-tests.md"
RECIPE = ROOT / "commands" / "sdlc-wave.md"


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
    git(repo, "add", "seed.txt")
    git(repo, "commit", "-q", "-m", "seed")


class WorktreeFailClosedTests(unittest.TestCase):
    """Pure-git fail-closed cases for the commands/sdlc-wave.md worktree recipe.

    commands/sdlc-wave.md line ~14 pins the exact recipe under test:
        git worktree add ../<repo>-wt-<seed-id> -b work/<seed-id>-<slug>
    This repo bundles no dispatcher, so each case below issues that literal
    git invocation against a disposable fixture repo built fresh under
    tempfile.TemporaryDirectory (never this checkout), and checks whether the
    raw command leaves the fixture's worktree/branch state byte-identical to
    its pre-attempt state after a refusal, per the fail-closed contract in
    skills/agentic-sdlc/references/worktree-failclosed-tests.md.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "fixture-repo"
        self.repo.mkdir()
        init_fixture(self.repo)

    def test_a_occupied_branch_refuses_and_leaves_no_orphan(self) -> None:
        """Executes worktree-failclosed-tests.md Failure-mode catalog #1 (Occupied isolation branch)."""
        branch = "work/s1-x"
        first = self.repo.parent / "fixture-repo-wt-s1-first"
        second = self.repo.parent / "fixture-repo-wt-s1-second"
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
        target = self.repo.parent / "fixture-repo-wt-s2"
        target.mkdir()
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
        target = self.repo.parent / "fixture-repo-wt-s3"

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


if __name__ == "__main__":
    unittest.main()
