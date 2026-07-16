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
    ROOT / "skills" / "agentic-sdlc" / "SKILL.md",
    ROOT / "skills" / "agentic-sdlc" / "references" / "sdlc-loop.md",
    ROOT / "skills" / "agentic-sdlc" / "references" / "seeds-worktrees.md",
    ROOT / "skills" / "agentic-sdlc" / "references" / "delegation-planes.md",
    ROOT / "skills" / "agentic-sdlc" / "references" / "mission-loop.md",
    ROOT / "skills" / "agentic-sdlc" / "references" / "tiered-orchestration.md",
]

UNSAFE_AUTHORITY_PATTERNS = (
    re.compile(r"(?i)\ba local status authorizes a remote push\b"),
    re.compile(
        r"(?i)\b(?:a\s+)?local\s+status\s+(?:authori[sz](?:e|es|ed)?|grants?)\s+(?:a\s+)?(?:remote\s+)?(?:push|outward\s+effect)\b"
    ),
    re.compile(
        r"(?i)\b(?:a\s+)?(?:green|passing)\s+gate\s+(?:authori[sz](?:e|es|ed)?|grants?)\s+(?:a\s+)?(?:remote\s+)?(?:push|outward\s+effect)\b"
    ),
    re.compile(
        r"(?i)\b(?:the\s+)?final\s+verdict\s+(?:authori[sz](?:e|es|ed)?|grants?|delegates?)\s+(?:ship\s+authority|(?:a\s+)?(?:remote\s+)?(?:push|outward\s+effect)|remote\s+authorization)\b"
    ),
)
UNSAFE_AUTHORITY_MUTATIONS = (
    "A local status authorizes a remote push.",
    "A green gate authorizes a remote push.",
    "The final verdict authorizes remote authorization.",
)


class AuthorityCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.surface_text = {
            path: path.read_text()
            for path in SURFACES
        }
        cls.text = "\n".join(cls.surface_text.values())

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

    def test_conductor_captures_read_only_artifacts_and_owns_seeds(self) -> None:
        flagship = (ROOT / "skills" / "agentic-sdlc" / "SKILL.md").read_text()
        mission = (
            ROOT
            / "skills"
            / "agentic-sdlc"
            / "references"
            / "mission-loop.md"
        ).read_text()
        self.assertRegex(flagship, r"(?is)read-only worker.{0,100}conductor persists")
        self.assertNotRegex(flagship, r"(?i)every delegated worker to write")
        self.assertRegex(mission, r"(?i)conductor is the sole queue writer")
        self.assertRegex(mission, r"(?is)workers and the critique team.{0,80}never.{0,40}mutate Seeds")
        self.assertNotRegex(mission, r"(?i)critique team.{0,80}files findings as classified Seeds")

    def test_every_surface_rejects_unsafe_authority_claims(self) -> None:
        for path, text in self.surface_text.items():
            with self.subTest(surface=path):
                self._assert_safe_authority(text)

    def _assert_safe_authority(self, text: str) -> None:
        for pattern in UNSAFE_AUTHORITY_PATTERNS:
            self.assertIsNone(
                pattern.search(text),
                f"unsafe authority claim: {pattern.pattern}",
            )

    def test_mutation_of_local_status_claim_is_caught(self) -> None:
        target = next(iter(self.surface_text.values()))
        for mutation in UNSAFE_AUTHORITY_MUTATIONS:
            with self.subTest(mutation=mutation):
                with self.assertRaises(AssertionError):
                    self._assert_safe_authority(target + "\n" + mutation)


if __name__ == "__main__":
    unittest.main()
