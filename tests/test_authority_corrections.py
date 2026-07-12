from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SURFACES = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "commands" / "sdlc-frame.md",
    ROOT / "commands" / "sdlc-init.md",
    ROOT / "commands" / "sdlc-wave.md",
    ROOT / "commands" / "sdlc-mission.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "SKILL.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "sdlc-loop.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "seeds-worktrees.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "delegation-planes.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "mission-loop.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "tiered-orchestration.md",
]


class AuthorityCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = "\n".join(path.read_text() for path in SURFACES)

    def test_public_loop_preserves_frame_wave_mission(self) -> None:
        for name in ("sdlc-frame", "sdlc-wave", "sdlc-mission"):
            self.assertIn(name, self.text)

    def test_roles_and_verdicts_are_advisory(self) -> None:
        self.assertRegex(self.text, r"(?i)recommend(?:ation|ed|s)")
        self.assertRegex(self.text, r"(?i)advis(?:ory|e|es)")
        self.assertRegex(self.text, r"(?i)worker.{0,80}(?:claim|report).{0,80}(?:not|never).{0,40}(?:authority|accept|close|done)")
        self.assertNotRegex(self.text, r"(?m)^\s*(?:SHIP|CLEAN|SHIP-WITH-NITS)\s*$")

    def test_init_is_a_reviewed_runbook_not_a_deterministic_engine(self) -> None:
        init = (ROOT / "commands" / "sdlc-init.md").read_text()
        self.assertRegex(init, r"(?i)reviewed runbook")
        self.assertRegex(init, r"(?i)(?:not|until).{0,80}(?:portable|executable|deterministic|engine)")
        self.assertRegex(init, r"(?i)cannot|conflict.{0,60}stop")
        self.assertNotRegex(init, r"(?i)deterministically (?:activates|initializes|configures)")

    def test_capabilities_fail_closed(self) -> None:
        self.assertRegex(self.text, r"(?i)not Git-ready")
        self.assertRegex(self.text, r"(?i)(?:missing|unpinned|untrusted|ambiguous).{0,100}(?:capabil|readiness|Git-ready)")
        self.assertRegex(self.text, r"(?i)capabilit(?:y|ies).{0,100}(?:probe|negotiate|verify|readback)")
        self.assertNotRegex(self.text, r"(?i)mise is the sole prerequisite")
        self.assertNotRegex(self.text, r"(?i)absence.{0,50}(?:never blocks|never weakens).{0,80}(?:capabil|readiness|wave)")

    def test_model_resolution_is_honest(self) -> None:
        self.assertRegex(self.text, r"(?i)requested.{0,100}model.{0,100}(?:resolved|inherited|unresolved)")
        self.assertRegex(self.text, r"(?i)(?:record|report).{0,100}(?:resolved|inherited/unresolved)")
        self.assertRegex(self.text, r"(?i)decorative model pin")
        self.assertNotRegex(self.text, r"(?i)model.{0,50}(?:proves|guarantees).{0,50}(?:quality|execution|resolution)")

    def test_outward_effects_need_operation_specific_authorization(self) -> None:
        self.assertRegex(self.text, r"(?i)operation-specific(?: user| maintainer)? approval")
        self.assertRegex(self.text, r"(?i)(?:push|publish|merge|PR|deployment).{0,120}(?:explicit|exact).{0,80}authori")
        self.assertRegex(self.text, r"(?i)(?:status|gate|reviewer|critic|conductor).{0,100}(?:does not|never).{0,100}(?:authori|grant)")
        self.assertRegex(self.text, r"(?i)integrator.{0,100}(?:delegated mutation|authorized fan-in)")


if __name__ == "__main__":
    unittest.main()
