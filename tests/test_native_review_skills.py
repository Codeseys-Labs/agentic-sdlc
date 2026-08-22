import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH_SKILL = ROOT / "skills" / "dispatching-exact-ocx-models" / "SKILL.md"
OVERENGINEERING_SKILL = ROOT / "skills" / "reviewing-overengineering" / "SKILL.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"


class ExactOcxDispatchSkillTests(unittest.TestCase):
    def test_skill_pins_the_two_dispatch_surfaces_and_fail_closed_receipt(self) -> None:
        self.assertTrue(DISPATCH_SKILL.is_file(), "the exact OCX dispatch skill must exist")
        text = DISPATCH_SKILL.read_text(encoding="utf-8")
        normalized = " ".join(text.split()).casefold()

        for contract in (
            "RuntimeAssignment",
            "resolution_state: resolved",
            "generated `ocx-*` Agent types",
            "public `model` argument is a placeholder",
            "every `agent()` call",
            "exact `model` and `effort`",
            "Muse tool names must be at most 64 characters",
            "requested identity is not readback",
            "no verified receipt, no dispatch",
            "Recurs; needs sequencing; has repeated failure modes; has stable input/output; benefits from explicit handoff",
        ):
            self.assertIn(contract.casefold(), normalized)


class OverengineeringReviewSkillTests(unittest.TestCase):
    def test_skill_requires_deletion_pressure_and_safety_rebuttal_on_one_snapshot(self) -> None:
        self.assertTrue(OVERENGINEERING_SKILL.is_file(), "the overengineering review skill must exist")
        text = OVERENGINEERING_SKILL.read_text(encoding="utf-8")
        normalized = " ".join(text.split()).casefold()

        for contract in (
            "immutable snapshot",
            "different model or independent perspective",
            "essential safety complexity",
            "accidental complexity removable now",
            "speculative functionality to defer",
            "deletion pressure",
            "safety-preservation rebuttal",
            "identity, consent, privacy, budgets, bounded execution, artifact integrity, or authority boundaries",
            "keep / delete / defer / remediate",
            "remediation creates a new candidate",
            "ponytail may complement this skill but is never a dependency",
            "recurs; needs sequencing; has repeated failure modes; has stable input/output; benefits from explicit handoff",
        ):
            self.assertIn(contract.casefold(), normalized)

    def test_first_class_skill_inventories_name_both_skills(self) -> None:
        for path in (README, AGENTS):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIn("skills/dispatching-exact-ocx-models/", text)
                self.assertIn("skills/reviewing-overengineering/", text)


if __name__ == "__main__":
    unittest.main()
