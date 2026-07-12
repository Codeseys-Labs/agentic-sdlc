from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
METHOD = ROOT / "skills" / "stacked-prs" / "SKILL.md"
GH = ROOT / "skills" / "stacked-prs-gh-cli" / "SKILL.md"


class PrSafetyDoctrineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.methodology = METHOD.read_text()
        cls.gh_cli = GH.read_text()
        cls.text = f"{cls.methodology}\n{cls.gh_cli}"

    def test_removes_automatic_retarget_assumptions(self) -> None:
        for document in (self.methodology, self.gh_cli):
            self.assertNotRegex(document, re.compile(r"auto[- ]retarget|automatically retarget", re.I))
            self.assertNotRegex(document, re.compile(r"GitHub (?:already )?retargeted|retargets? .* automatically", re.I))

    def test_requires_saved_boundaries_and_exact_lease(self) -> None:
        for phrase in (
            "old boundaries",
            "saved remote OID",
            "--force-with-lease=refs/heads/<branch>:<saved-remote-oid>",
            "target drift",
            "invalidate",
        ):
            self.assertIn(phrase, self.text)
        self.assertNotRegex(self.text, re.compile(r"--force-with-lease origin", re.I))
        self.assertNotIn("git push --force origin", self.text)

    def test_requires_ordered_retarget_requery_restack_and_review(self) -> None:
        for pattern in (
            r"explicitly retarget each immediate child",
            r"re-query `baseRefName`, `headRefName`, and PR `state`",
            r"cascade the\s+restack through every descendant",
            r"squash merge",
            r"Re-gate and re-review",
            r"final race check",
        ):
            self.assertRegex(self.text, pattern)

        order = [
            self.text.index("old boundaries"),
            self.text.index("explicitly retarget each immediate child"),
            self.text.index("re-query `baseRefName`, `headRefName`, and PR `state`"),
            self.text.index("cascade the\n  restack through every descendant"),
            self.text.index("Re-gate and re-review"),
            self.text.index("final race check"),
        ]
        self.assertEqual(order, sorted(order))

    def test_branch_deletion_waits_for_open_pr_base_usage(self) -> None:
        self.assertIn("Do not delete a branch while any open PR still uses it as a base", self.text)
        self.assertIn("re-query all open PRs", self.text)
        self.assertIn("baseRefName", self.text)

    def test_governance_unknown_is_fail_closed(self) -> None:
        for phrase in (
            "evidence is absent",
            "HTTP 403",
            "unsupported governance fields",
            "do not treat UNKNOWN as approval",
        ):
            self.assertIn(phrase, self.text)

    def test_candidate_is_invalidated_by_target_drift(self) -> None:
        self.assertRegex(self.text, r"target/base/head or PR state drifts")
        self.assertIn("re-gate, and re-review", self.text)


if __name__ == "__main__":
    unittest.main()
