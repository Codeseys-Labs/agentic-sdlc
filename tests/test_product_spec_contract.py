from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PLAN_DIR = ROOT / "docs" / "plans" / "claude-code-first-harness"
SPEC = PLAN_DIR / "agentic-sdlc-product-spec.md"
HANDOFF = PLAN_DIR / "to-spec-handoff.md"

# The five Core-owned Claude commands (to-spec-handoff.md "Claude commands").
CORE_COMMANDS = frozenset(
    {
        "/sdlc-init",
        "/sdlc-frame",
        "/sdlc-wave",
        "/sdlc-mission",
        "/sdlc-rightsize",
    }
)

# The exact `ccodex sdlc` namespace, in order. The brief (to-spec-handoff.md:174-181) enumerated
# eight; the 2026-08-23 operator decision moved `rightsize` to the agent plane, so the re-issued
# spec pins seven (Implementation Decision 91) and the seven remain a subset of the brief's block.
#
# THESE SEVEN ARE THE BRIEF-SOURCED LINES, and that is now a narrower claim than "the block"
# (agentic-sdlc-a010, relaxed 2026-08-26). The predicates below used to require Implementation
# Decision 91's fenced block to equal this tuple exactly AND every member of it to appear verbatim
# in the immutable brief, which made the block subtractable but not extendable: the spec could drop
# `ccodex sdlc inspect` and still pass, while a line recording the ratified top-level surface
# (`ccodex install --scope user --agent claude`, gh #8 / gh #11) could not be added at all, because
# a brief written before the ratification cannot be its source. Provenance is therefore asserted
# over the `ccodex sdlc` lines, which the brief really is the source of, and the block may carry
# lines whose source is the ratification record instead. Both teeth stay: no brief-sourced line may
# vanish, and no EIGHTH `ccodex sdlc` verb may arrive.
NAMESPACE_LINES = (
    "ccodex sdlc inspect",
    "ccodex sdlc doctor",
    "ccodex sdlc install --host claude",
    "ccodex sdlc status",
    "ccodex sdlc update",
    "ccodex sdlc recover",
    "ccodex sdlc uninstall",
)
SDLC_VERBS = frozenset(line.split()[2] for line in NAMESPACE_LINES)
NAMESPACE_PREFIX = "ccodex sdlc"

# The spec's structure. Pinned so a reworded second gate cannot arrive as a new section.
TOP_LEVEL_HEADINGS = (
    "Problem Statement",
    "Solution",
    "User Stories",
    "Implementation Decisions",
    "Testing Decisions",
    "Build Slices",
    "Release Validity",
    "Out of Scope",
    "Further Notes",
)

# AC6 has two halves: provenance AND no-supersession. Patterns are whitespace-tolerant
# because this document wraps prose, so these phrases straddle line breaks.
AUTHORITY_PATTERNS = (
    r"derived\s+from\s+the\s+source\s+brief\s+and\s+does\s+not\s+supersede",
    r"return\s+to\s+product\s+decision\s+work",
)

# The load-bearing obligation each slice's exit artifact must keep, traced to the brief.
# Labels alone are not enough: softening the text is the realistic regression.
EXIT_OBLIGATIONS = {
    1: "negative claim fixtures",
    2: "before any mutating verb exists",
    3: "preserve foreign state",
    4: "applied activation commit or a named refusal",
    5: "terminal wave receipt",
    6: "readable against Git history",
    7: "return to native-only state",
    8: "none enabled by default",
    9: "one certified Core tuple",
}

# The ten fixture classes every build slice carries, proportional to its effects.
FIXTURE_CLASSES = (
    "offline positive",
    "malformed",
    "conflict",
    "stale-prestate",
    "substitution",
    "redaction",
    "crash",
    "partial-effect",
    "recovery",
    "non-authority",
)

PROVENANCE_TARGETS = ("to-spec-handoff.md", "map.md")

# The 2026-08-23 re-issue's honesty pins: the ADR status sentence must state ADR-0025's
# supersession, never the pre-re-issue blanket acceptance claim, and Implementation Decision 61
# must keep the six-outcome vocabulary the ADR-0030 amendment restored.
SUPERSESSION_SENTENCE = "ADR-0025 is superseded by ADR-0030"
RETIRED_ADR_CLAIM = "ADR-0022 through ADR-0027 are accepted"
WAVE_OUTCOMES = (
    "`accepted`",
    "`remediation-progress`",
    "`blocked`",
    "`aborted`",
    "`failed`",
    "`unknown-effect`",
)

IMPLEMENTATION_DECISIONS_HEADING = "## Implementation Decisions"
TESTING_DECISIONS_HEADING = "## Testing Decisions"
RELEASE_VALIDITY_HEADING = "## Release Validity"
BUILD_SLICES_HEADING = "## Build Slices"
RELEASE_GATE_PHRASE = "invalid unless all"
RETIRED_GATE_PHRASE = "A stable release requires"
RELEASE_SPINE_CONDITIONS = 11
BUILD_SLICE_COUNT = 9


def missing(text: str, tokens) -> list[str]:
    """Tokens absent from text. ponytail: substring match, not a Markdown parser."""
    return [token for token in tokens if token not in text]


def section_body(text: str, heading: str) -> str:
    """Text from `heading` up to the next top-level heading (empty when absent)."""
    match = re.search(
        rf"^{re.escape(heading)}$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    return match.group(1) if match else ""


def numbered_item(text: str, heading: str, number: int) -> str:
    """One numbered item's body from one section. Scoped, because User Stories,
    Implementation Decisions, and Testing Decisions all number from 1."""
    match = re.search(
        rf"^{number}\. (.*?)(?=^\d+\. |^## |\Z)",
        section_body(text, heading),
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def slice_blocks(text: str) -> list[str]:
    body = section_body(text, BUILD_SLICES_HEADING)
    return re.split(r"^### ", body, flags=re.MULTILINE)[1:]


def declared_commands(text: str) -> set[str]:
    return set(re.findall(r"/sdlc-[a-z-]+", text))


def preamble(text: str) -> str:
    """Everything above the first top-level section."""
    return text.split("\n## ", 1)[0]


def namespace_block(text: str) -> list[str]:
    """The fenced block inside Implementation Decision 91, verbatim lines."""
    match = re.search(
        r"^91\. \*\*`ccodex sdlc` namespace\.\*\*.*?```text\n(.*?)```",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return [line.strip() for line in match.group(1).strip().splitlines()] if match else []


def command_spans(text: str) -> list[str]:
    """Every span of this document that is a command spelling rather than prose.

    Two shapes, which are the only two this document uses for a command: an inline code span, and a
    fenced block's body. Fences are scanned deliberately — ID 91's ```text block is exactly where an
    extra verb would be smuggled — and inline spans are scanned because that is the house style for
    naming a verb in a sentence.

    The fence pattern admits LEADING WHITESPACE, and that is load-bearing rather than tidy: ID 91 is
    a numbered list item, so its fence is indented four spaces, and an anchored ``^```` skipped the
    one block this closure exists to police. `test_smuggling_an_extra_verb_is_detected` is the case
    that catches a regression here.
    """
    fences = re.findall(r"^[ \t]*```[a-z]*\n(.*?)^[ \t]*```", text, re.MULTILINE | re.DOTALL)
    inline = re.findall(r"`([^`\n]+)`", text)
    return [*fences, *inline]


def stray_verbs(text: str) -> set[str]:
    """Any `ccodex sdlc <verb>` outside the seven, in a COMMAND context. Case-tolerant.

    Restricted to `command_spans` since agentic-sdlc-a010. What it used to do was scan the whole
    document with a wrap-tolerant `\\s+`, which meant the token after the phrase was captured
    wherever the phrase appeared — so the sentence this train has to be able to write, "`ccodex
    sdlc` is retired", reported a stray verb `is`, and the same misfire waited for every prose
    mention of the retired namespace.

    The accepted tradeoff INVERTS rather than disappearing, and the new side is the better one: an
    un-backticked bare-prose `ccodex sdlc rightsize` is now a false negative where a bare-prose
    caption used to be a false positive. This document backticks or fences every command it names —
    the assertion below on the seven brief-sourced lines is over a fenced block — so the shape that
    is no longer covered is one the house style does not produce, while the shape that used to
    misfire is one the retirement prose requires. Wrap tolerance goes with it: a command spelling
    does not straddle a line break inside a code span.
    """
    seen: set[str] = set()
    for span in command_spans(text):
        seen |= {v.lower() for v in re.findall(r"(?i)ccodex sdlc ([a-z][a-z-]*)", span)}
    return seen - SDLC_VERBS


def top_level_headings(text: str) -> list[str]:
    return re.findall(r"^## (.+)$", text, re.MULTILINE)


def normalized(text: str) -> str:
    """Collapse whitespace, so an assertion survives re-wrapping."""
    return re.sub(r"\s+", " ", text).strip()


def exit_artifacts(text: str) -> dict[int, str]:
    """Each slice's exit artifact body, keyed by slice number."""
    found: dict[int, str] = {}
    for block in slice_blocks(text):
        number = re.match(r"Slice (\d+)", block)
        body = re.search(
            r"- \*\*Exit artifact:\*\* (.*?)(?=\n- |\n### |\Z)", block, re.DOTALL
        )
        if number and body:
            found[int(number.group(1))] = normalized(body.group(1))
    return found


def count_bullets(body: str) -> int:
    return len(re.findall(r"^- ", body, re.MULTILINE))


class ProductSpecContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = SPEC.read_text(encoding="utf-8")

    def test_command_surface_is_exactly_the_five_core_commands(self) -> None:
        """Closure, not membership: an extra /sdlc-* command is also a defect."""
        self.assertEqual(CORE_COMMANDS, declared_commands(self.spec))

    def test_namespace_block_enumerates_the_seven_verbs_in_order(self) -> None:
        """Enumeration, not vocabulary: dropping a line from the block is a defect
        even when the verb is still mentioned in prose elsewhere.

        Scoped to the block's `ccodex sdlc` lines since agentic-sdlc-a010, so the block may also
        record the ratified top-level surface that replaced the namespace. What is unchanged is the
        part that has teeth: these seven, all of them, in this order, and no eighth."""
        self.assertEqual(
            list(NAMESPACE_LINES),
            [line for line in namespace_block(self.spec) if line.startswith(NAMESPACE_PREFIX)],
        )

    def test_no_verb_exists_outside_the_namespace(self) -> None:
        """Closure: a smuggled extra verb fails even capitalized. Since the 2026-08-23
        decision this includes `rightsize`, which lives on the agent plane and must not
        reappear under `ccodex sdlc`."""
        self.assertEqual(set(), stray_verbs(self.spec))

    def test_structure_is_exactly_the_nine_sections(self) -> None:
        """Pinned so a reworded second gate cannot arrive as a new section."""
        self.assertEqual(list(TOP_LEVEL_HEADINGS), top_level_headings(self.spec))

    def test_declares_provenance_and_authority(self) -> None:
        """Both halves of AC6: the links AND the no-supersession rule."""
        head = preamble(self.spec)
        self.assertEqual([], missing(head, PROVENANCE_TARGETS))
        for pattern in AUTHORITY_PATTERNS:
            self.assertRegex(head, pattern)

    def test_assembles_the_release_acceptance_spine_as_one_gate(self) -> None:
        body = section_body(self.spec, RELEASE_VALIDITY_HEADING)
        self.assertNotEqual("", body, "spec must carry a single release-validity gate")
        self.assertEqual(RELEASE_SPINE_CONDITIONS, count_bullets(body))
        self.assertIn(RELEASE_GATE_PHRASE, body)

    def test_no_competing_release_gate_exists(self) -> None:
        """Uniqueness: exactly one gate, and the retired phrasing stays retired."""
        self.assertEqual(1, self.spec.count(RELEASE_GATE_PHRASE))
        self.assertNotIn(RETIRED_GATE_PHRASE, self.spec)

    def test_every_slice_carries_scope_and_exit_artifact(self) -> None:
        blocks = slice_blocks(self.spec)
        self.assertEqual(BUILD_SLICE_COUNT, len(blocks))
        for block in blocks:
            title = block.splitlines()[0]
            self.assertIn("**Scope:**", block, title)
            self.assertIn("**Exit artifact:**", block, title)

    def test_exit_artifacts_keep_their_sourced_obligations(self) -> None:
        """Content, not labels: softening an exit artifact is the realistic regression."""
        found = exit_artifacts(self.spec)
        self.assertEqual(set(EXIT_OBLIGATIONS), set(found))
        for number, obligation in EXIT_OBLIGATIONS.items():
            self.assertIn(normalized(obligation), found[number], f"slice {number}")

    def test_fixture_classes_are_bound_by_testing_decision_39(self) -> None:
        """Binding, not presence: the classes must live in TD 39, not merely in the file."""
        item = numbered_item(self.spec, TESTING_DECISIONS_HEADING, 39)
        self.assertNotEqual("", item, "spec must carry Testing Decision 39")
        self.assertEqual([], missing(item, FIXTURE_CLASSES))
        self.assertIn("proportional", item)
        self.assertIn("slice", item)

    def test_declares_the_adr_supersession_and_not_the_retired_blanket_claim(self) -> None:
        """DIV-2's repair: the spec states ADR-0025's supersession by ADR-0030 and no
        longer carries the pre-re-issue blanket acceptance sentence."""
        self.assertIn(SUPERSESSION_SENTENCE, self.spec)
        self.assertNotIn(RETIRED_ADR_CLAIM, self.spec)

    def test_decision_61_keeps_the_six_outcome_vocabulary(self) -> None:
        """Retention pin for the vocabulary the ADR-0030 amendment restored: all six
        wave outcomes stay closed inside Implementation Decision 61."""
        item = numbered_item(self.spec, IMPLEMENTATION_DECISIONS_HEADING, 61)
        self.assertNotEqual("", item, "spec must carry Implementation Decision 61")
        self.assertEqual([], missing(item, WAVE_OUTCOMES))

    def test_handoff_remains_the_cited_source_of_the_brief_sourced_lines(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        handoff = HANDOFF.read_text(encoding="utf-8")
        self.assertTrue(CORE_COMMANDS <= declared_commands(handoff))
        # A deliberate subset: the brief's block carries the eighth line the 2026-08-23
        # decision withdrew, so the seven pinned lines must all trace to it.
        #
        # PROVENANCE IS ASSERTED OVER THESE SEVEN, not over whatever the spec's block holds
        # (agentic-sdlc-a010). The brief predates the front-door ratification, so a spec line naming
        # the ratified top-level surface has the ratification record as its source and cannot trace
        # here; requiring it to was what made the block unextendable. The direction that matters
        # still holds: a `ccodex sdlc` line the spec declares without the brief behind it fails.
        self.assertEqual([], missing(handoff, NAMESPACE_LINES))
        # Closure is asserted on the spec only. The brief is an immutable source, and
        # its Mermaid node label `[ccodex sdlc lifecycle]` is a caption, not a verb.


class ProductSpecMutationTests(unittest.TestCase):
    """Planted violations: every assertion above must fail on a degraded spec."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = SPEC.read_text(encoding="utf-8")

    def test_dropping_a_command_is_detected(self) -> None:
        mutated = self.spec.replace("/sdlc-rightsize", "")
        self.assertNotEqual(CORE_COMMANDS, declared_commands(mutated))

    def test_adding_a_stray_command_is_detected(self) -> None:
        mutated = self.spec.replace("/sdlc-wave", "/sdlc-wave and /sdlc-deploy", 1)
        self.assertNotEqual(CORE_COMMANDS, declared_commands(mutated))

    def test_dropping_a_verb_from_the_block_is_detected(self) -> None:
        """Dropped from the enumeration is a defect even while prose survives."""
        mutated = self.spec.replace("    ccodex sdlc uninstall\n", "")
        self.assertNotEqual(list(NAMESPACE_LINES), namespace_block(mutated))

    def test_smuggling_an_extra_verb_is_detected(self) -> None:
        """The realistic regression since 2026-08-23: the withdrawn eighth verb creeps
        back into the block."""
        mutated = self.spec.replace(
            "    ccodex sdlc uninstall",
            "    ccodex sdlc uninstall\n    ccodex sdlc rightsize",
            1,
        )
        self.assertNotEqual(set(), stray_verbs(mutated))
        self.assertNotEqual(list(NAMESPACE_LINES), namespace_block(mutated))

    def test_a_capitalized_stray_verb_in_a_command_span_is_detected(self) -> None:
        """Case tolerance, in the context the house style puts a command in."""
        mutated = self.spec + "\nRun `ccodex sdlc Publish` to promote a candidate.\n"
        self.assertNotEqual(set(), stray_verbs(mutated))

    def test_a_stray_verb_in_an_indented_fence_is_detected(self) -> None:
        """The indented-fence hole, pinned as its own case.

        ID 91's fence is indented four spaces because the decision is a numbered list item. An
        anchored fence pattern silently stopped scanning it, which would have made the closure
        assertion above vacuous over exactly the block it is for.
        """
        mutated = self.spec + "\n1. A decision.\n\n    ```text\n    ccodex sdlc publish\n    ```\n"
        self.assertEqual({"publish"}, stray_verbs(mutated))

    def test_the_retirement_SENTENCE_is_not_a_verb_site(self) -> None:
        """THE RELAXATION'S OWN CONTROL (agentic-sdlc-a010): prose about the retired namespace passes.

        This is the sentence the front-door train has to be able to write, and the pre-relaxation
        predicate reported a stray verb `is` for it. Asserting it here means a future retightening
        that re-broke the sentence fails as a named case instead of blocking a doc wave again.
        """
        mutated = self.spec + "\nThe `ccodex sdlc` namespace is retired; the verbs are top-level.\n"
        self.assertEqual(set(), stray_verbs(mutated))

    def test_the_ratified_top_level_surface_may_join_the_block(self) -> None:
        """The second half of the relaxation: the block is extendable, not just subtractable.

        A line naming the ratified surface traces to gh #8 / gh #11 rather than to the pre-ratified
        brief, so it must be addable without the provenance predicate rejecting it — while the seven
        brief-sourced lines stay enumerated, in order, and closed against an eighth.
        """
        mutated = self.spec.replace(
            "    ccodex sdlc uninstall",
            "    ccodex sdlc uninstall\n    ccodex install --scope user --agent claude",
            1,
        )
        self.assertEqual(set(), stray_verbs(mutated))
        self.assertEqual(
            list(NAMESPACE_LINES),
            [line for line in namespace_block(mutated) if line.startswith(NAMESPACE_PREFIX)],
        )
        self.assertIn("ccodex install --scope user --agent claude", namespace_block(mutated))

    def test_a_bare_prose_stray_verb_is_the_accepted_blind_spot(self) -> None:
        """The tradeoff, asserted rather than left implicit.

        Restricting the scan to command spans trades a false positive on prose for a false negative
        on an un-backticked mention. The trade is only defensible if it is visible, so both halves
        run here on ONE planting: the same text is missed as bare prose and caught the moment it is
        spelled the way this document spells a command.
        """
        planting = "ccodex sdlc publish promotes a candidate."
        self.assertEqual(set(), stray_verbs(f"{self.spec}\n{planting}\n"))
        self.assertEqual({"publish"}, stray_verbs(f"{self.spec}\n`{planting}`\n"))

    def test_a_reworded_second_gate_is_detected(self) -> None:
        """Uniqueness by structure, not by phrase: a new section fails the heading list."""
        mutated = self.spec.replace(
            "\n## Out of Scope",
            "\n## Preview Validity\n\nA preview release must satisfy every condition below.\n"
            "\n## Out of Scope",
            1,
        )
        self.assertNotEqual(list(TOP_LEVEL_HEADINGS), top_level_headings(mutated))

    def test_stripping_the_authority_sentences_is_detected(self) -> None:
        """The half of AC6 that filename links alone cannot carry."""
        head = preamble(self.spec)
        mutated = self.spec.replace(head, "\n".join(head.splitlines()[:8]))
        for pattern in AUTHORITY_PATTERNS:
            self.assertNotRegex(preamble(mutated), pattern)

    def test_restoring_the_retired_release_gate_is_detected(self) -> None:
        mutated = self.spec + "\n- A stable release requires exact installed-byte journeys.\n"
        self.assertIn(RETIRED_GATE_PHRASE, mutated)
        self.assertNotIn(RETIRED_GATE_PHRASE, self.spec)

    def test_a_second_release_gate_is_detected(self) -> None:
        mutated = self.spec + "\nA preview release is invalid unless all of these hold.\n"
        self.assertNotEqual(1, mutated.count(RELEASE_GATE_PHRASE))

    def test_dropping_a_spine_condition_is_detected(self) -> None:
        body = section_body(self.spec, RELEASE_VALIDITY_HEADING)
        first_bullet = re.search(r"^- .*$", body, re.MULTILINE)
        assert first_bullet is not None
        mutated = section_body(
            self.spec.replace(first_bullet.group(0), ""), RELEASE_VALIDITY_HEADING
        )
        self.assertNotEqual(RELEASE_SPINE_CONDITIONS, count_bullets(mutated))

    def test_hollowing_out_a_slice_is_detected(self) -> None:
        """A heading with no fields must fail, so the count is not vacuous."""
        mutated = self.spec.replace(
            "- **Exit artifact:** a demonstrated return to native-only state.", ""
        )
        blocks = slice_blocks(mutated)
        self.assertFalse(all("**Exit artifact:**" in block for block in blocks))

    def test_unbinding_the_fixture_classes_is_detected(self) -> None:
        mutated = self.spec.replace("proportional to its\n    effects", "as needed")
        self.assertNotIn("proportional", numbered_item(mutated, TESTING_DECISIONS_HEADING, 39))

    def test_weakening_an_exit_artifact_is_detected(self) -> None:
        """The reviewer's mutation: slice 3 softened until it no longer implies
        foreign-state preservation."""
        mutated = self.spec.replace(
            "- **Exit artifact:** effect-aware lifecycle exits that preserve foreign state.",
            "- **Exit artifact:** lifecycle verbs implemented.",
        )
        self.assertNotIn(EXIT_OBLIGATIONS[3], exit_artifacts(mutated)[3])

    def test_dropping_provenance_is_detected(self) -> None:
        mutated = self.spec.replace("to-spec-handoff.md", "")
        self.assertNotEqual([], missing(mutated, PROVENANCE_TARGETS))

    def test_reasserting_the_retired_adr_claim_is_detected(self) -> None:
        """The pre-re-issue regression: the supersession sentence reverts to the
        blanket acceptance claim that ADR-0025's supersession falsified."""
        mutated = self.spec.replace(
            SUPERSESSION_SENTENCE,
            "ADR-0017 through ADR-0020 and ADR-0022 through ADR-0027 are accepted "
            "product constraints",
        )
        self.assertIn(RETIRED_ADR_CLAIM, mutated)
        self.assertNotIn(SUPERSESSION_SENTENCE, mutated)

    def test_narrowing_the_wave_outcomes_is_detected(self) -> None:
        """The ADR-0030 pre-amendment regression: an honesty outcome silently leaves
        Implementation Decision 61's closed set."""
        mutated = self.spec.replace("`unknown-effect`", "`unknown`")
        item = numbered_item(mutated, IMPLEMENTATION_DECISIONS_HEADING, 61)
        self.assertNotEqual([], missing(item, WAVE_OUTCOMES))


if __name__ == "__main__":
    unittest.main()
