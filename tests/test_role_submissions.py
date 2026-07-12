from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CLAUDE_DIR = ROOT / "agents" / "claude"
CODEX_DIR = ROOT / "agents" / "codex"
ROLE_NAMES = (
    "cartographer",
    "planner",
    "implementer",
    "reviewer",
    "critic",
    "integrator",
    "researcher",
)
READ_ONLY_ROLES = ("cartographer", "planner", "reviewer", "critic", "researcher")


class RoleSubmissionContractTests(unittest.TestCase):
    def read_claude(self, role: str) -> str:
        return (CLAUDE_DIR / f"sdlc-{role}.md").read_text()

    def read_codex(self, role: str) -> tuple[str, dict]:
        path = CODEX_DIR / f"sdlc-{role}.toml"
        text = path.read_text()
        return text, tomllib.loads(text)

    def assert_submission_contract(self, text: str) -> None:
        self.assertIn("STRUCTURED SUBMISSION", text)
        for field in (
            "role",
            "scope",
            "findings",
            "evidence",
            "recommendation",
            "blockers",
            "unknowns",
            "next_action",
        ):
            self.assertRegex(text, rf"(?m)^\s*[-*]?\s*`?{field}`?\b")
        self.assertIn("conductor", text.lower())
        self.assertIn("authorization", text.lower())

    def test_every_role_declares_structured_submission(self) -> None:
        for role in ROLE_NAMES:
            with self.subTest(host="claude", role=role):
                self.assert_submission_contract(self.read_claude(role))
            with self.subTest(host="codex", role=role):
                text, config = self.read_codex(role)
                self.assert_submission_contract(text)
                self.assertIn("developer_instructions", config)

    def test_read_only_roles_cannot_decide_or_mutate(self) -> None:
        forbidden = re.compile(
            r"(?i)\b(?:decide|authorize|merge|push|publish|delete|execute)\b.*\b(?:you|role|worker)\b"
        )
        for role in READ_ONLY_ROLES:
            for host, text in (("claude", self.read_claude(role)), ("codex", self.read_codex(role)[0])):
                with self.subTest(host=host, role=role):
                    self.assertIn("recommendation", text.lower())
                    self.assertNotRegex(text, forbidden)
                    self.assertNotRegex(text, r"(?m)^\s*`?(?:SHIP|CLEAN|APPROVED|BLOCK)`?\s*$")

    def test_reviewer_and_critic_recommendations_are_not_verdicts(self) -> None:
        for role in ("reviewer", "critic"):
            for host, text in (("claude", self.read_claude(role)), ("codex", self.read_codex(role)[0])):
                with self.subTest(host=host, role=role):
                    self.assertIn("recommend", text.lower())
                    self.assertIn("conductor", text.lower())
                    self.assertRegex(text, r"(?i)do not .*decide|never .*decide|not .*authority")
                    self.assertNotIn("verdict: `SHIP`", text)
                    self.assertNotIn("verdict: SHIP", text)

    def test_only_integrator_can_execute_authorized_fanin(self) -> None:
        for role in ROLE_NAMES:
            for host, text in (("claude", self.read_claude(role)), ("codex", self.read_codex(role)[0])):
                with self.subTest(host=host, role=role):
                    if role == "integrator":
                        self.assertRegex(text, r"(?i)only .*integrator.*(?:execute|mutation)")
                        self.assertRegex(text, r"(?i)already[- ]authorized")
                        self.assertRegex(text, r"(?i)never .*user.*authority|does not .*user.*authority")
                    else:
                        self.assertNotRegex(text, r"(?i)only .*integrator.*(?:execute|mutation)")

    def test_hosts_keep_role_names_and_submission_capture_guidance(self) -> None:
        for role in ROLE_NAMES:
            claude = self.read_claude(role)
            codex, config = self.read_codex(role)
            self.assertIn(f"sdlc-{role}", claude)
            self.assertEqual(config["name"], f"sdlc-{role}")
            self.assertIn("capture", claude.lower())
            self.assertIn("capture", codex.lower())


if __name__ == "__main__":
    unittest.main()
