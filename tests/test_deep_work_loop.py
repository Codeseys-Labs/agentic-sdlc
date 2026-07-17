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
        "independent review of an immutable candidate.",
    ),
}

# --- Subject-agnostic loop-authority guard --------------------------------
# The doc must never grant ANY subject (a phase, a step, a worker, the loop
# itself, or a bare imperative) push/publish/merge/deploy/release/integrate
# authority. A fixed subject alternation lets realistic drift escape, so this
# mirrors the grammar approach of the queue-mutation scanner in
# test_preflight_capabilities.py: find every affirmative grant of an outward
# verb, then drop the ones an explicit negation guards. Only base verb forms
# are matched, so descriptive/negated prose ("never merges, publishes, pushes")
# and object lists ("humans alone authorize push, publication, merge") stay
# clean; the imperative form must be flagged.
OUTWARD_VERB = r"(?:push|publish|merge|deploy|release|integrate)"

# Affirmative modal/authorization immediately (± up to two adverbs) before an
# outward verb: "may push", "is authorized to deploy", "can publish".
AFFIRMATIVE_AUTHORITY_GRANT = re.compile(
    r"(?i)\b(?:may|might|can|could|will|shall|should|"
    r"is\s+authorized\s+to|are\s+authorized\s+to|"
    r"is\s+permitted\s+to|are\s+permitted\s+to|"
    r"is\s+allowed\s+to|are\s+allowed\s+to|"
    r"is\s+free\s+to|are\s+free\s+to)\s+"
    rf"(?:\w+\s+){{0,2}}?{OUTWARD_VERB}\b"
)
# Clause-initial bare imperative directing an outward action on an object:
# "Once green, push the branch", ". Merge the worktree".
BARE_IMPERATIVE_GRANT = re.compile(
    rf"(?i)(?:^|[.;:]\s+|,\s+){OUTWARD_VERB}\s+(?:the|a|an|its|your|this|that|all|it)\b"
)
# A negation anywhere in the short window ending at the match neutralizes it:
# "may not push", "is never permitted to merge", "no worker may deploy".
AUTHORITY_NEGATION = re.compile(r"(?i)\b(?:not|never|no|cannot|without|neither|nor)\b")


def loop_authority_grants(text: str) -> list[str]:
    """Return affirmative, non-negated grants of outward/fan-in authority.

    Whitespace is normalized first so prose line-wrapping cannot split a grant
    across a newline and hide it from the window checks.
    """
    normalized = " ".join(text.split())
    grants: list[str] = []
    for pattern in (AFFIRMATIVE_AUTHORITY_GRANT, BARE_IMPERATIVE_GRANT):
        for match in pattern.finditer(normalized):
            window = normalized[max(0, match.start() - 24) : match.end()]
            if AUTHORITY_NEGATION.search(window):
                continue
            grants.append(match.group(0).strip())
    return grants


# The reviewer's escaped-drift phrasings (subject varies; verb varies; one is a
# bare imperative) plus a release variant — every one must be flagged.
FORBIDDEN_AUTHORITY_MUTATIONS = (
    "The reconcile phase may push the branch and merge the worktree once gates are green.",
    "The act phase is authorized to deploy the release to production.",
    "Each phase may merge its own worktree after gates pass.",
    "The verify step can publish the package to the registry.",
    "Once green, push the branch and open the PR.",
    "The deep-work loop may push directly to main.",
    "A worker is permitted to release the build once its lane is green.",
)
# The doc's own negated disclaimer must stay clean under the same guard.
CLEAN_NEGATED_AUTHORITY = (
    "The loop never merges, publishes, pushes, or deploys, and never mutates the queue itself."
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
        # The clean doc grants no outward/fan-in authority to any subject.
        self.assertEqual(loop_authority_grants(self.doc), [])
        # And the conductor/integrator authority split is stated positively.
        lowered = self.doc.lower()
        self.assertIn("conductor", lowered)
        self.assertIn("integrator", lowered)

    def test_authority_guard_is_subject_agnostic_over_reviewer_drift(self) -> None:
        # Every one of the reviewer's escaped phrasings — phase-subject grants,
        # a bare imperative, and a release variant — must now be flagged, even
        # when appended into an otherwise-clean copy of the doc.
        for phrasing in FORBIDDEN_AUTHORITY_MUTATIONS:
            with self.subTest(phrasing=phrasing):
                self.assertTrue(
                    loop_authority_grants(phrasing),
                    f"guard missed an outward-authority grant: {phrasing!r}",
                )
                mutated = self.doc + "\n" + phrasing + "\n"
                self.assertTrue(
                    loop_authority_grants(mutated),
                    f"guard missed drift injected into the doc: {phrasing!r}",
                )
        # The negated disclaimer the doc actually uses is the clean case.
        self.assertEqual(loop_authority_grants(CLEAN_NEGATED_AUTHORITY), [])
        self.assertIn(CLEAN_NEGATED_AUTHORITY, " ".join(self.doc.split()))

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
