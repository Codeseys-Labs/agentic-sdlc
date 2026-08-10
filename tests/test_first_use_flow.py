from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
README = ROOT / "README.md"
SKILL = ROOT / "skills" / "agentic-sdlc" / "SKILL.md"
FRAME = ROOT / "commands" / "sdlc-frame.md"
WAVE = ROOT / "commands" / "sdlc-wave.md"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def assert_direct_exception_contract(test: unittest.TestCase, text: str) -> None:
    """Assert the narrow no-route exception cannot become a spawn bypass."""
    test.assertRegex(text, r"(?i)no certified delegation route")
    test.assertRegex(text, r"(?i)exactly one.{0,100}bounded.{0,100}non-delegated conductor execution")
    test.assertRegex(text, r"(?i)one clean.{0,80}Git worktree")
    test.assertRegex(text, r"(?i)zero workers")
    test.assertRegex(text, r"(?i)zero model spawns")
    test.assertRegex(text, r"(?i)(?:no|zero) `RuntimeAssignment` claim")
    for phase in ("scope", "acceptance criteria", "gate", "review", "reconcil"):
        test.assertRegex(text, rf"(?i){phase}")
    test.assertRegex(
        text,
        r"(?i)stop.{0,180}(?:second direct pass|retry|worker/model|parallel|unbounded)",
    )


class ProgressiveFirstUseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = normalized(README)
        cls.skill = normalized(SKILL)
        cls.frame = normalized(FRAME)
        cls.wave = normalized(WAVE)

    def test_hello_world_journey_uses_the_minimum_concepts_and_command_cross_links(self) -> None:
        self.assertIn("## First task: a small hello world", self.readme)
        self.assertIn("Seeds** is the project's durable work queue", self.readme)
        self.assertIn("**Frame** is the short plan", self.readme)
        self.assertIn("**Wave** is the reviewed worktree execution", self.readme)
        self.assertIn('/sdlc-frame Add a hello command that prints "hello"', self.readme)
        for path in ("commands/sdlc-init.md", "commands/sdlc-frame.md", "commands/sdlc-wave.md"):
            with self.subTest(path=path):
                self.assertIn(f"]({path})", self.readme)

    def test_absent_queue_always_routes_to_activation_and_stops(self) -> None:
        for path, text in ((README, self.readme), (SKILL, self.skill), (FRAME, self.frame), (WAVE, self.wave)):
            with self.subTest(surface=path):
                self.assertRegex(text, r"(?i)(?:Seeds queue is absent|has no Seeds queue).{0,160}/sdlc-init")
                self.assertRegex(text, r"(?i)(?:Seeds queue is absent|has no Seeds queue).{0,220}\bstop\b")
        self.assertRegex(self.frame, r"(?i)Frame does not initialize a queue or improvise activation")
        self.assertRegex(self.wave, r"(?i)Wave does not initialize a queue or improvise activation")

    def test_every_actual_worker_or_model_spawn_keeps_certified_delegation_boundary(self) -> None:
        for path, text in ((README, self.readme), (SKILL, self.skill), (FRAME, self.frame)):
            with self.subTest(surface=path):
                self.assertRegex(
                    text,
                    r"(?i)actual worker or model spawn.{0,220}(?:certified|RuntimeAssignment)",
                )
        self.assertRegex(
            self.wave,
            r"(?i)conductor must supply.{0,100}certified `RuntimeAssignment`.{0,100}before spawn",
        )
        for text in (self.skill, self.frame):
            with self.subTest(surface=text[:32]):
                self.assertRegex(text, r"(?i)stop.{0,180}(?:inherited|unresolved|unverified)")
        self.assertRegex(
            self.wave,
            r"(?i)(?:inherited|unresolved|unverified).{0,180}stop before dispatch and spawn",
        )

    def test_direct_exception_is_bounded_non_delegated_and_preserves_wave_controls(self) -> None:
        for path, text in ((README, self.readme), (SKILL, self.skill), (FRAME, self.frame)):
            with self.subTest(surface=path):
                assert_direct_exception_contract(self, text)

    def test_wave_refuses_to_relabel_a_worker_as_direct_execution(self) -> None:
        self.assertRegex(
            self.wave,
            r"(?i)if no certified delegation route exists, stop this Wave; do not reinterpret a worker as direct execution",
        )
        self.assertRegex(
            self.wave,
            r"(?i)bounded non-delegated conductor execution.{0,160}zero workers.{0,100}zero model spawns",
        )

    def test_direct_exception_contract_is_falsifiable(self) -> None:
        with self.assertRaises(AssertionError):
            assert_direct_exception_contract(
                self,
                self.frame.replace("zero workers", "one worker", 1),
            )
        with self.assertRaises(AssertionError):
            assert_direct_exception_contract(
                self,
                self.frame.replace("zero model spawns", "one model spawn", 1),
            )


if __name__ == "__main__":
    unittest.main()
