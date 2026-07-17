from __future__ import annotations

import re
import unittest
from pathlib import Path

# Reuse the shipped-surface scanner helpers that the preflight-capabilities
# surface tests use, rather than re-implementing the Seeds-authority grammar.
from test_preflight_capabilities import (
    guidance_violations,
    literal_guidance_lines,
    seeds_mutation_operations,
)


ROOT = Path(__file__).parents[1]
FLAGSHIP = ROOT / "skills" / "agentic-sdlc"
SKILL = FLAGSHIP / "SKILL.md"
DOC = FLAGSHIP / "references" / "deep-work-loop.md"
TIERED = FLAGSHIP / "references" / "tiered-orchestration.md"
MODEL_TIER_SKILL = ROOT / "skills" / "model-tier-rightsizing" / "SKILL.md"

# The consolidated loop shape: seven named phases in canonical order.
CANONICAL_LOOP = "frame → map/research → decide → act → verify → critique → reconcile"
PHASES = ("frame", "map/research", "decide", "act", "verify", "critique", "reconcile")

# Distinctive, load-bearing long sentences that OWN their doctrine in the
# tiered-orchestration reference and the model-tier-rightsizing skill. The
# consolidated loop reference must POINT to them, never copy them wholesale
# (mirrors the A3 generator's doctrine-duplication guard).
DOCTRINE_ANCHORS = {
    TIERED: (
        "Keep scale-setting work singular: a frame, plan, authority analysis, cross-system invariant,",
        "Every delegated workstream has a bounded artifact, owner, stop condition, wrong-output",
        "A verdict may recommend one scoped re-entry to an earlier phase when evidence reveals a gap.",
    ),
    MODEL_TIER_SKILL: (
        "Route the consequence of a wrong answer, not task prestige or marketing rank.",
        "A task moves down only when a real gate changes its failure from silent damage to a",
    ),
}

# A loop/worker/lens must never grant ITSELF outward or fan-in authority. The
# legitimate "an authorized integrator alone performs an already-authorized
# fan-in" sentence names the integrator, not these subjects, so it stays clean.
LOOP_SELF_AUTHORITY = re.compile(
    r"(?i)\b(?:the loop|this loop|a worker|workers|the critique|a lens|any lens|a recommendation)\b"
    r".{0,80}\b(?:may|can|is\s+authorized\s+to|are\s+authorized\s+to)\b"
    r".{0,80}\b(?:merge|integrate|fan-in|fan\s+in|publish|push|deploy|mutate\s+the\s+queue)\b"
)


class DeepWorkLoopReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.skill = SKILL.read_text(encoding="utf-8")
        # Whitespace-normalized copy for phrase checks that must survive prose
        # line-wrapping (mirrors the README/AGENTS mise-prerequisite check).
        cls.normalized = " ".join(cls.doc.split())
        cls.normalized_lower = cls.normalized.lower()

    def test_reference_exists_and_skill_routes_to_it(self) -> None:
        self.assertTrue(DOC.is_file(), f"missing reference: {DOC}")
        # SKILL.md routes to the consolidated reference (validate_bundle then
        # requires the file to exist, so the route can never dangle).
        self.assertIn("references/deep-work-loop.md", self.skill)

    def test_seven_loop_phases_present_by_name_and_in_canonical_order(self) -> None:
        self.assertIn(CANONICAL_LOOP, self.doc)
        for phase in PHASES:
            with self.subTest(phase=phase):
                self.assertIn(phase, self.doc.lower())

    def test_doc_carries_no_bare_sd_or_non_conductor_queue_mutation_guidance(self) -> None:
        # Reuse the exact shipped-surface scanner, scoped to this one doc.
        violations = guidance_violations(
            DOC.relative_to(ROOT),
            literal_guidance_lines(DOC),
            enforce_seeds_authority=True,
        )
        self.assertEqual(violations, [], "\n".join(violations))
        # The whole-document sweep agrees: no positive queue-mutation operation.
        self.assertEqual(seeds_mutation_operations(self.doc), [])

    def test_queue_mutation_scanner_is_falsifiable(self) -> None:
        # The guard actually fires on injected mutation guidance.
        self.assertTrue(seeds_mutation_operations("Workers may create a Seeds issue."))

    def test_doc_is_seedproposal_only_and_names_the_single_queue(self) -> None:
        self.assertIn("SeedProposal", self.doc)
        # Explicitly disclaims a competing queue of its own.
        self.assertIn("no second queue", self.doc.lower())

    def test_doc_grants_no_publication_or_integration_authority(self) -> None:
        self.assertNotRegex(self.doc, LOOP_SELF_AUTHORITY)
        # Falsifiability: the guard fires on a mutated copy (§G1.8 pattern).
        mutated = self.doc + "\nThe loop may merge the integration branch.\n"
        self.assertRegex(mutated, LOOP_SELF_AUTHORITY)
        # And the conductor/integrator authority split is stated positively.
        lowered = self.doc.lower()
        self.assertIn("conductor", lowered)
        self.assertIn("integrator", lowered)

    def test_doc_states_the_bounded_delegation_depth_cap(self) -> None:
        self.assertRegex(self.normalized_lower, r"delegation.{0,80}(?:cap|bound)")
        self.assertIn("no unbounded recursive delegation", self.normalized_lower)

    def test_effort_routing_names_the_three_lanes_and_defers_to_model_tier(self) -> None:
        lowered = self.doc.lower()
        for lane in ("frontier", "judgment", "volume"):
            with self.subTest(lane=lane):
                self.assertIn(lane, lowered)
        # Defers to the canonical model-tier doctrine rather than restating it.
        self.assertIn("model-tier-rightsizing", self.doc)
        # [1m] is client context/compaction behavior, not an intelligence claim.
        self.assertIn("[1m]", self.doc)
        self.assertIn("compaction", lowered)
        self.assertRegex(self.normalized_lower, r"\[1m\].{0,200}not.{0,60}intelligence")

    def test_doc_names_its_integration_points(self) -> None:
        # Seeds (SeedProposal only), the git-change-flow router, and the loop
        # references it consolidates are all named as single-hop pointers.
        for pointer in (
            "references/git-change-flow.md",
            "references/sdlc-loop.md",
            "references/mission-loop.md",
            "references/tiered-orchestration.md",
        ):
            with self.subTest(pointer=pointer):
                self.assertIn(pointer, self.doc)

    def test_doc_does_not_duplicate_source_pinned_doctrine(self) -> None:
        for source, anchors in DOCTRINE_ANCHORS.items():
            source_text = source.read_text(encoding="utf-8")
            for anchor in anchors:
                with self.subTest(source=source.name, anchor=anchor[:40]):
                    # The anchor is a real, distinctive line in its owning file...
                    self.assertIn(anchor, source_text)
                    # ...and is NOT copied wholesale into the loop reference.
                    self.assertNotIn(anchor, self.doc)


if __name__ == "__main__":
    unittest.main()
