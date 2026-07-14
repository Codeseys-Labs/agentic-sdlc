from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ROUTER = ROOT / "skills" / "model-tier-rightsizing" / "SKILL.md"
CALIBRATION = (
    ROOT
    / "skills"
    / "model-tier-rightsizing"
    / "references"
    / "model-routing-calibration.md"
)
FLAGSHIP = (
    ROOT
    / "skills"
    / "agentic-sdlc-orchestrator"
    / "references"
    / "tiered-orchestration.md"
)
EXACT_MODELS = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
)
ROADMAP_LANES = (
    "S1 Seeds toolchain retention",
    "S2 Seeds execution contract",
    "Seeds fan-in",
    "Wave 1 CAO deletion",
    "Wave 2 state-v3 identity cutover",
    "Claude marketplace/plugin plane",
    "Local checkout rename gate",
    "GitHub repository rename gate",
    "A1 change-writing",
    "A2 Git-default sdlc-init",
    "A3 hierarchical instructions",
    "R1 shared role contracts",
    "R2 bounded Deep Work Loop",
    "R3 HyperResearch/Research OS",
    "G1 Git change-flow family",
    "G2 toolchain/security",
    "J1 jj certification",
    "J2 jj implementation",
    "A2j jj init amendment",
    "M0a Mermaid browser ADR/spike",
    "M0b Mermaid security foundation",
    "M1 structural Mermaid skills",
    "M2 planning Mermaid skills",
    "M3 quantitative Mermaid skills",
    "M4 technical Mermaid skills",
    "M5 conceptual Mermaid skills",
    "M6 Mermaid router",
    "M7 Mermaid conformance",
    "Release hardening",
    "Evolutionary Core M2",
    "Claude Golden Wave M3",
    "Portability M4",
    "CCP/ccodex certification",
    "Final family wiring",
)


class ModelTierRightsizingTests(unittest.TestCase):
    def test_router_is_concise_attribution_free_and_points_to_one_authority(self) -> None:
        text = ROUTER.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]

        self.assertLessEqual(len(text.splitlines()), 100)
        self.assertEqual(text.count("references/model-routing-calibration.md"), 1)
        self.assertNotRegex(frontmatter, r"(?m)^(?:author|model|agent|version|date):")
        self.assertNotRegex(text, r"(?i)(?:written|generated|authored) by (?:an? )?(?:model|agent|Claude)")
        for consequence in ("derail", "degrade", "retry"):
            self.assertIn(consequence, text.lower())
        for requirement in ("exact model ID", "requested", "resolved", "fallback", "gate"):
            self.assertIn(requirement, text)
        for model in EXACT_MODELS:
            self.assertNotIn(model, text)

    def test_canonical_reference_pins_transport_and_evidence_boundaries(self) -> None:
        text = CALIBRATION.read_text(encoding="utf-8")

        for model in EXACT_MODELS:
            self.assertIn(f"`{model}`", text)
        for effort in ("low", "medium", "high", "xhigh", "max"):
            self.assertRegex(text, rf"(?m)^- `{effort}`$")
        for unsafe in (
            "global.anthropic.claude-fable-5",
            "us.anthropic.claude-opus-4-8",
            "global.anthropic.claude-sonnet-5",
        ):
            self.assertIn(f"`{unsafe}`", text)

        self.assertRegex(text, r"(?i)requested effort.{0,200}resolved effort")
        self.assertRegex(text, r"(?i)resolved effort.{0,80}(?:unknown|unavailable|not exposed)")
        self.assertRegex(text, r"(?is)\[1m\].{0,160}(?:compaction|context handling)")
        self.assertRegex(text, r"(?is)\[1m\].{0,200}(?:does not|never).{0,80}(?:intelligence|upstream 1M|context window)")
        self.assertIn("80 task-local passes", text)
        self.assertIn("10 harness-inconclusive cells", text)
        self.assertIn("0 observed task-local model failures", text)
        self.assertRegex(text, r"(?i)not (?:a )?(?:total )?ranking")
        self.assertRegex(text, r"(?i)not production proof")
        self.assertRegex(text, r"(?i)provisional.{0,100}requested-only")

    def test_canonical_reference_covers_roadmap_fallbacks_quotas_and_receipts(self) -> None:
        text = CALIBRATION.read_text(encoding="utf-8")

        for lane in ROADMAP_LANES:
            self.assertIn(lane, text)
        for heading in (
            "## Complementary vendor roles",
            "## Fallback and escalation",
            "## Quota and concurrency evidence",
            "## Rerun triggers",
            "## Auditable evidence receipts",
        ):
            self.assertIn(heading, text)

        self.assertIn("2026-07-05", text)
        for inherited_quota in ("200K", "30M", "6M", "720M", "43.2B", "8.64B"):
            self.assertIn(inherited_quota, text)
        self.assertRegex(text, r"(?i)no (?:Sol, Terra, or Luna|GPT).{0,80}quota.{0,80}(?:evidence|measured|available)")
        for receipt in (
            "agentic-sdlc-six-tier-smoke/v1",
            "wf_a120305a-ab6",
            "wf_4baaadfe-431",
            "wf_c7260fad-96e",
            "1f413019d765b220284bbedfd5fb580eb0d50a7670b2d55444cf964177c08213",
            "dbb2e2f5a98bcf4e6eeb62312e8b45db88788119",
            "d6bb02b79a5d3362e4a28e3ae5c43c0f105f8eed",
        ):
            self.assertIn(receipt, text)

    def test_flagship_is_provider_neutral_and_delegates_calibration(self) -> None:
        text = FLAGSHIP.read_text(encoding="utf-8")

        self.assertIn("model-tier-rightsizing", text)
        self.assertIn("model-routing-calibration", text)
        self.assertRegex(text, r"(?i)does not duplicate.{0,80}(?:matrix|model calibration)")
        for model in EXACT_MODELS:
            self.assertNotIn(model, text)
        self.assertIsNone(
            re.search(r"(?i)\b(?:Fable|Opus|Sonnet|Sol|Terra|Luna)\b", text),
            "flagship orchestration doctrine must remain provider/model neutral",
        )


if __name__ == "__main__":
    unittest.main()
