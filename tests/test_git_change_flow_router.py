from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
FLAGSHIP = ROOT / "skills" / "agentic-sdlc"
ROUTER = FLAGSHIP / "references" / "git-change-flow.md"
SEEDS_WORKTREES = FLAGSHIP / "references" / "seeds-worktrees.md"
PR_SAFETY_TEST = "test_pr_safety_doctrine.py"

# The eleven change-flow invariants of spec §G1.5, each keyed by a stable
# keyword that must appear on a dispatch row that also names an authoritative
# file. A twelfth row folds the effect-idempotency cross-reference (§G1.6).
INVARIANTS = (
    "one-writer ownership",
    "recovery refs",
    "rebase boundary",
    "squash scope",
    "clean-apply",
    "stack topology",
    "remote-oid lease",
    "child-pr deletion",
    "merge-base footprint",
    "re-gating",
    "final race check",
)

# Forbidden re-teaching: the router dispatches, it never carries the exact
# command strings the skills own. These are the load-bearing command literals
# that test_pr_safety_doctrine.py asserts live INSIDE the two skills.
FORBIDDEN_COMMAND_STRINGS = (
    "--force-with-lease=refs/heads/<branch>:<saved-remote-oid>",
    "git rebase --onto",
)

# SURFACES tuple (mirrors test_jj_retirement.py:13-33 shape): the files that
# must all remain present as SKILL.md / router after consolidation. A
# "demote to compat alias" refactor that deleted a SKILL.md would drop it from
# validator coverage (spec §G1.4) and fail here.
SURFACES = (
    ROOT / "skills" / "stacked-prs" / "SKILL.md",
    ROOT / "skills" / "stacked-prs-gh-cli" / "SKILL.md",
    ROUTER,
)


class GitChangeFlowRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router = ROUTER.read_text(encoding="utf-8")
        cls.seeds_worktrees = SEEDS_WORKTREES.read_text(encoding="utf-8")

    def _dispatch_rows(self) -> list[str]:
        # Rows that both dispatch (name a .md site) and carry doctrine text.
        return [line for line in self.router.splitlines() if ".md" in line]

    def test_router_exists_and_maps_every_invariant(self) -> None:
        rows = "\n".join(self._dispatch_rows()).lower()
        for invariant in INVARIANTS:
            with self.subTest(invariant=invariant):
                # Each invariant appears on a dispatch row that names a site.
                self.assertIn(invariant, rows)
        # The router states the methodology-vs-mechanics split and that the
        # duplication between the two skills is deliberate + conformance-required.
        lowered = self.router.lower()
        self.assertIn("methodology", lowered)
        self.assertIn("mechanics", lowered)
        self.assertIn("deliberate", lowered)
        self.assertIn(PR_SAFETY_TEST, self.router)
        # The effect-idempotency cross-reference (§G1.6) is present as a row.
        self.assertIn("reconcile", lowered)

    def test_router_does_not_reteach_doctrine(self) -> None:
        for command in FORBIDDEN_COMMAND_STRINGS:
            with self.subTest(command=command):
                self.assertNotIn(command, self.router)

    def test_scatter_sites_only_point(self) -> None:
        block = self.seeds_worktrees.split("Dependent Seeds", 1)
        self.assertEqual(len(block), 2, "scatter block marker missing")
        region = block[1].split("\n## ", 1)[0]
        # The scatter site points at the router...
        self.assertIn("git-change-flow.md", region)
        # ...and does not re-teach the mechanics.
        self.assertNotIn("--force-with-lease", region)
        self.assertNotIn("rebase --onto", region)

    def test_both_skills_still_enumerated_as_skill_md(self) -> None:
        for path in SURFACES:
            with self.subTest(surface=path):
                self.assertTrue(path.is_file(), f"missing surface: {path}")

    def test_router_paths_are_post_rename(self) -> None:
        self.assertNotIn("agentic-sdlc-orchestrator", self.router)
        # Every flagship-reference path the router names is post-rename and exists.
        referenced = sorted(set(re.findall(r"skills/[A-Za-z0-9._/-]+\.md", self.router)))
        self.assertTrue(referenced, "router names no site paths")
        for rel in referenced:
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).is_file(), f"router names a dead path: {rel}")
        for rel in referenced:
            if rel.startswith("skills/agentic-sdlc"):
                self.assertTrue(rel.startswith("skills/agentic-sdlc/"))

    def test_router_rejects_force_push_language(self) -> None:
        force_push = re.compile(r"git push --force origin", re.I)
        # The clean router passes the never-force doctrine guard...
        self.assertNotRegex(self.router, force_push)
        # ...and the guard actually fires on a mutated copy (falsifiability, §G1.8).
        mutated = self.router + "\ngit push --force origin <branch>\n"
        self.assertRegex(mutated, force_push)


if __name__ == "__main__":
    unittest.main()
