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

# The exact `ccodex sdlc` namespace, in order (to-spec-handoff.md:174-181).
NAMESPACE_LINES = (
    "ccodex sdlc inspect",
    "ccodex sdlc doctor",
    "ccodex sdlc install --host claude",
    "ccodex sdlc status",
    "ccodex sdlc update",
    "ccodex sdlc recover",
    "ccodex sdlc uninstall",
    "ccodex sdlc rightsize",
)
SDLC_VERBS = frozenset(line.split()[2] for line in NAMESPACE_LINES)

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
    4: "write-ready, remediation-ready, or refused",
    5: "terminal wave receipt",
    6: "read-only projections",
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


def stray_verbs(text: str) -> set[str]:
    """Any `ccodex sdlc <verb>` outside the eight. Case- and wrap-tolerant, so a
    verb smuggled in across a line break or capitalized is still visible.
    ponytail: a generic mention must use backticked `ccodex sdlc` house style, or it
    registers as a stray verb. Known, accepted tradeoff — the realistic trigger is a
    descriptive caption, e.g. a Mermaid node label `[ccodex sdlc lifecycle]`. If the
    spec gains a diagram, exclude ```mermaid fences specifically. Do NOT exclude all
    fences: that would hide a ninth verb smuggled into ID 91's ```text block."""
    seen = {v.lower() for v in re.findall(r"(?i)ccodex\s+sdlc\s+([a-z][a-z-]*)", text)}
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

    def test_namespace_block_enumerates_the_eight_verbs_in_order(self) -> None:
        """Enumeration, not vocabulary: dropping a line from the block is a defect
        even when the verb is still mentioned in prose elsewhere."""
        self.assertEqual(list(NAMESPACE_LINES), namespace_block(self.spec))

    def test_no_verb_exists_outside_the_namespace(self) -> None:
        """Closure: a smuggled ninth verb fails even split across a line wrap
        or capitalized."""
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

    def test_handoff_remains_the_cited_source_of_every_addition(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        handoff = HANDOFF.read_text(encoding="utf-8")
        self.assertTrue(CORE_COMMANDS <= declared_commands(handoff))
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
        """Dropped from the enumeration while a prose mention survives."""
        mutated = self.spec.replace("    ccodex sdlc rightsize\n", "")
        self.assertNotEqual(list(NAMESPACE_LINES), namespace_block(mutated))

    def test_smuggling_a_ninth_verb_is_detected(self) -> None:
        mutated = self.spec.replace(
            "    ccodex sdlc rightsize", "    ccodex sdlc rightsize\n    ccodex sdlc publish", 1
        )
        self.assertNotEqual(set(), stray_verbs(mutated))
        self.assertNotEqual(list(NAMESPACE_LINES), namespace_block(mutated))

    def test_a_wrap_split_ninth_verb_is_detected(self) -> None:
        """A verb hidden across a line break, which this document's wrapping invites."""
        mutated = self.spec + "\nThe ccodex sdlc\npublish verb promotes a candidate.\n"
        self.assertNotEqual(set(), stray_verbs(mutated))

    def test_a_capitalized_ninth_verb_is_detected(self) -> None:
        mutated = self.spec + "\nccodex sdlc Publish promotes a candidate.\n"
        self.assertNotEqual(set(), stray_verbs(mutated))

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


if __name__ == "__main__":
    unittest.main()
