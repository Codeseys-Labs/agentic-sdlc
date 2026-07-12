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
        cls.documents = {
            "stacked-prs": METHOD.read_text(),
            "stacked-prs-gh-cli": GH.read_text(),
        }

    def test_each_skill_independently_obeys_safety_doctrine(self) -> None:
        for name, document in self.documents.items():
            with self.subTest(skill=name):
                # Retargeting is an explicit, queried operation, never an assumed platform action.
                self.assertNotRegex(document, re.compile(r"auto[- ]retarget|automatically retarget", re.I))
                self.assertNotRegex(document, re.compile(r"retargets? .* automatically", re.I))
                self.assertIn("explicitly retarget each immediate child", document.lower())
                self.assertIn("re-query", document)

                # Every descendant keeps its own old boundary and is rewritten bottom-up.
                self.assertIn("every old parent boundary", document)
                self.assertIn("old-parent map", document)
                self.assertIn("new-parent map", document)
                self.assertIn("git rebase --onto <new-parent> <saved-old-parent> <child>", document)
                self.assertRegex(document, re.compile(r"cascade (?:from the parent outward|bottom-up)"))
                self.assertRegex(document, re.compile(r"never (?:replay|replays) .*ancestor(?: commits| range)?", re.I | re.S))

                # Rewrites and deletion both use a lease tied to the saved remote OID.
                self.assertIn("--force-with-lease=refs/heads/<branch>:<saved-remote-oid>", document)
                self.assertIn(
                    "git push --force-with-lease=refs/heads/<branch>:<saved-remote-oid> origin :refs/heads/<branch>",
                    document,
                )
                self.assertNotRegex(document, re.compile(r"git push origin :refs/heads/<branch>", re.I))
                self.assertNotRegex(document, re.compile(r"git push --force origin", re.I))
                self.assertIn("ordinary unleased deletion", document)

                # Unknown governance and races fail closed immediately before mutation.
                self.assertIn("governance is unknown", document.lower())
                self.assertIn("unknown is not approval", document.lower())
                self.assertIn("final race check", document)
                self.assertIn("immediately before", document)
                self.assertIn("saved remote OID", document)
                self.assertIn("required checks", document)
                self.assertIn("changed", document)

    def test_each_skill_requires_fresh_retarget_readback_and_review(self) -> None:
        for name, document in self.documents.items():
            with self.subTest(skill=name):
                self.assertRegex(
                    document,
                    re.compile(r"re-query `baseRefName`, `headRefName`, and `state`", re.I),
                )
                self.assertIn("fresh review", document)
                self.assertIn("re-gate", document)
                self.assertRegex(document, re.compile(r"target/base/head/state drift invalidates|target/base/head.*state.*invalidates", re.I))


if __name__ == "__main__":
    unittest.main()
