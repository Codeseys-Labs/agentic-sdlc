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
EXPECTED_SUBMISSION_HEADINGS = (
    "role",
    "scope",
    "findings",
    "evidence",
    "recommendation",
    "blockers",
    "unknowns",
    "next_action",
)
SUBMISSION_SECTION = re.compile(
    r"(?ms)^## STRUCTURED SUBMISSION\s*$\n(?P<body>.*?)(?=^##\s|\Z)"
)
AUTHORIZED_FANIN_EXECUTION = re.compile(
    r"(?i)\balready[- ]authorized\b.*\bfan[- ]in\b.*\b(?:execute|perform|apply|merge|mutation)\b"
)
FINAL_VERDICT_TOKEN = re.compile(
    r"(?i)\b(?:SHIP(?:-WITH-NITS)?|CLEAN)\b"
)
FINAL_VERDICT_INSTRUCTION = re.compile(
    r"(?i)\b(?:verdict|release status|final decision)\s*[:=-]\s*"
    r"(?:APPROVED|BLOCK(?:ED)?|PASS|FAIL)\b|"
    r"\b(?:end|finish|conclude|return)\b.{0,40}\b"
    r"(?:APPROVED|BLOCK(?:ED)?|PASS|FAIL)\b"
)


class RoleSubmissionContractTests(unittest.TestCase):
    def read_claude(self, role: str) -> str:
        return (CLAUDE_DIR / f"sdlc-{role}.md").read_text()

    def read_codex(self, role: str) -> tuple[str, dict]:
        path = CODEX_DIR / f"sdlc-{role}.toml"
        text = path.read_text()
        return text, tomllib.loads(text)

    def submission_body(self, text: str) -> str:
        match = SUBMISSION_SECTION.search(text)
        self.assertIsNotNone(match, "missing delimited structured submission section")
        return match.group("body")

    def assert_submission_contract(self, text: str) -> None:
        body = self.submission_body(text)
        headings = tuple(re.findall(r"(?m)^\s*-\s*`([^`]+)`\s*:", body))
        self.assertEqual(headings, EXPECTED_SUBMISSION_HEADINGS)
        self.assertIn("conductor", body.lower())
        self.assertIn("authorization", body.lower())

    def assert_no_authorized_fanin_execution(self, text: str) -> None:
        self.assertNotRegex(text, AUTHORIZED_FANIN_EXECUTION)
        reversed_order = re.compile(
            r"(?i)\b(?:execute|perform|apply|merge)\b.*\balready[- ]authorized\b.*\bfan[- ]in\b"
        )
        self.assertNotRegex(text, reversed_order)

    def assert_no_final_verdict_instruction(self, text: str) -> None:
        self.assertNotRegex(text, FINAL_VERDICT_TOKEN)
        self.assertNotRegex(text, FINAL_VERDICT_INSTRUCTION)

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
                    self.assert_no_authorized_fanin_execution(text)
                    self.assertNotRegex(text, r"(?m)^\s*`?(?:SHIP|CLEAN|APPROVED|BLOCK)`?\s*$")

    def test_reviewer_and_critic_recommendations_are_not_verdicts(self) -> None:
        for role in ("reviewer", "critic"):
            for host, text in (("claude", self.read_claude(role)), ("codex", self.read_codex(role)[0])):
                with self.subTest(host=host, role=role):
                    self.assertIn("recommend", text.lower())
                    self.assertIn("conductor", text.lower())
                    self.assertRegex(text, r"(?i)do not .*decide|never .*decide|not .*authority")
                    self.assert_no_final_verdict_instruction(text)

                    # A forbidden instruction must be caught without mutating a role file.
                    for mutation in (
                        f"{text}\nEnd with SHIP.",
                        f"{text}\nEnd with CLEAN.",
                        f"{text}\nEnd with SHIP-WITH-NITS.",
                        f"{text}\nverdict: SHIP",
                    ):
                        with self.assertRaises(AssertionError):
                            self.assert_no_final_verdict_instruction(mutation)

    def test_only_integrator_can_execute_authorized_fanin(self) -> None:
        for role in ROLE_NAMES:
            for host, text in (("claude", self.read_claude(role)), ("codex", self.read_codex(role)[0])):
                with self.subTest(host=host, role=role):
                    if role == "integrator":
                        self.assertRegex(text, r"(?i)only .*integrator.*(?:execute|mutation)")
                        self.assertRegex(text, r"(?i)already[- ]authorized")
                        self.assertRegex(text, r"(?i)never .*user.*authority|does not .*user.*authority")
                    else:
                        self.assert_no_authorized_fanin_execution(text)
                        implementer_mutation = (
                            f"{text}\nOnly the implementer may execute an already-authorized "
                            "fan-in mutation."
                        )
                        with self.assertRaises(AssertionError):
                            self.assert_no_authorized_fanin_execution(implementer_mutation)

    def test_critics_are_advisory_and_cannot_mutate_seeds(self) -> None:
        for host, text, sandbox in (
            ("claude", self.read_claude("critic"), None),
            ("codex", self.read_codex("critic")[0], self.read_codex("critic")[1]["sandbox_mode"]),
        ):
            with self.subTest(host=host):
                self.assertRegex(text, r"(?i)seed-shaped recommendation")
                self.assertRegex(text, r"(?i)never invoke `sd`|never .*mutate the queue")
                self.assertNotRegex(text, r"(?i)file them|only writes are .*Seeds")
                if sandbox is not None:
                    self.assertEqual(sandbox, "read-only")

    def test_read_only_codex_roles_return_artifacts_for_conductor_capture(self) -> None:
        for role in ("cartographer", "planner"):
            text, config = self.read_codex(role)
            with self.subTest(role=role):
                self.assertEqual(config["sandbox_mode"], "read-only")
                self.assertRegex(text, r"(?is)return the complete .+?structured\s+submission")
                self.assertRegex(text, r"(?i)conductor persists")
                self.assertNotRegex(text, r"(?i)your only writes? (?:are|is)|write the .+ artifact")

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
