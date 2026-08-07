"""Conformance contract for the adr-lifecycle skill and the four reference-instead verdicts.

Mirrors tests/test_change_writing.py in shape. Two jobs:

1. Pin the adr-lifecycle skill's admission floor (name==dirname, description cap measured
   through the validator's own folding helpers, references resolve) and the doctrine claims
   its body must carry — the authority boundary, the immutability rule, and the neighbour
   naming that gate 1 of references/skill-authoring.md requires.
2. Pin the four capabilities that landed as references rather than top-level skills, so a
   later change that promotes one to skills/<name>/ has to delete an assertion deliberately
   instead of silently forking the incumbent that owns the ground.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]

SKILL = ROOT / "skills" / "adr-lifecycle" / "SKILL.md"
REFERENCES = {
    "house-template": SKILL.parent / "references" / "house-template.md",
    "lifecycle-states": SKILL.parent / "references" / "lifecycle-states.md",
    "review-and-antipatterns": SKILL.parent / "references" / "review-and-antipatterns.md",
    "relationships-and-index": SKILL.parent / "references" / "relationships-and-index.md",
    "adr-as-evidence": SKILL.parent / "references" / "adr-as-evidence.md",
}

# The four reference-instead verdicts, each under the skill that already owns its ground.
CHANGE_WRITING = ROOT / "skills" / "change-writing" / "SKILL.md"
FLAGSHIP = ROOT / "skills" / "agentic-sdlc" / "SKILL.md"
RESEARCH_OS = ROOT / "skills" / "codex-research-os" / "SKILL.md"

CONVENTIONAL_COMMITS = CHANGE_WRITING.parent / "references" / "conventional-commits.md"
WRITING_CLARITY = CHANGE_WRITING.parent / "references" / "technical-writing-clarity.md"
MERMAID_AUTHORING = FLAGSHIP.parent / "references" / "mermaid-authoring.md"
CLAIM_OBLIGATIONS = RESEARCH_OS.parent / "references" / "claim-obligations.md"
BOUNDED_LAB_LOOP = RESEARCH_OS.parent / "references" / "bounded-lab-loop.md"

REFERENCE_VERDICTS = {
    "conventional-commits": (CONVENTIONAL_COMMITS, CHANGE_WRITING),
    "technical-writing-clarity": (WRITING_CLARITY, CHANGE_WRITING),
    "mermaid-authoring": (MERMAID_AUTHORING, FLAGSHIP),
    "claim-obligations": (CLAIM_OBLIGATIONS, RESEARCH_OS),
    "bounded-lab-loop": (BOUNDED_LAB_LOOP, RESEARCH_OS),
}

ALL_NEW_FILES = (SKILL, *REFERENCES.values(), *(p for p, _ in REFERENCE_VERDICTS.values()))


def _frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return match.group(1) if match else ""


def _metadata_value(metadata: str, name: str) -> str:
    """Fold a YAML block scalar exactly as scripts/validate_bundle.py does.

    The description cap is enforced against the folded string, so measuring it any
    other way (len() on the raw frontmatter) would test a different number than the
    authoritative gate does.
    """
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", metadata, re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    if value not in {"|", ">", "|-", ">-"} and not re.fullmatch(r"[|>](?:[+-]?[1-9]|[1-9][+-]?)", value):
        return value
    continuation: list[str] = []
    lines = metadata[match.end():].splitlines()
    if lines and not lines[0]:
        lines = lines[1:]
    for line in lines:
        if not line.strip():
            continuation.append("")
            continue
        if not line.startswith((" ", "\t")):
            break
        continuation.append(line.strip())
    return " ".join(continuation).strip()


class AdrLifecycleSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL.read_text(encoding="utf-8") if SKILL.is_file() else ""

    def test_skill_and_references_exist(self) -> None:
        self.assertTrue(SKILL.is_file(), f"missing {SKILL}")
        for name, path in REFERENCES.items():
            with self.subTest(reference=name):
                self.assertTrue(path.is_file(), f"missing {path}")

    def test_frontmatter_name_matches_dir_and_description_bounded(self) -> None:
        metadata = _frontmatter(self.skill_text)
        self.assertEqual(_metadata_value(metadata, "name"), "adr-lifecycle")
        description = _metadata_value(metadata, "description")
        self.assertTrue(description, "description must be present")
        self.assertLessEqual(len(description), 1024)

    def test_description_names_its_nearest_neighbour(self) -> None:
        """Gate 1 of references/skill-authoring.md: the description alone must let a
        selector reject the nearest neighbour. change-writing owns commit/PR text; this
        skill owns decision records, and the description has to say so."""
        description = _metadata_value(_frontmatter(self.skill_text), "description")
        self.assertIn("change-writing", description)
        self.assertRegex(description, re.compile(r"commit", re.I))

    def test_no_static_model_or_effort_pin(self) -> None:
        for path in ALL_NEW_FILES:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, re.compile(r"(?im)^\s*model\s*[:=]"))
                self.assertNotRegex(text, re.compile(r"model_reasoning_effort"))

    def test_authority_boundary_declared(self) -> None:
        """Evidence is never authorization: the body must state it, and must not claim an
        accepted record authorizes an outward effect."""
        text = self.skill_text
        self.assertRegex(text, re.compile(r"never authoriz", re.I))
        self.assertRegex(text, re.compile(r"advisory evidence", re.I))
        for effect in ("push", "merge", "publication", "deployment"):
            with self.subTest(effect=effect):
                self.assertIn(effect, text)
        # No inversion: an accepted/passing/green/clean thing must never be said to GRANT
        # authority. Scoped per sentence, because the negation can sit anywhere in it —
        # before the subject ("no verdict ... authorizes"), between subject and verb ("does
        # not authorize"), or after ("authorizes nothing"). A sentence carrying any negation
        # is doctrine; one carrying none while naming a trigger word is an affirmative grant.
        grants = re.compile(r"(?i)\bauthoriz(?:es|e|ing)\b")
        negation = re.compile(r"(?i)\b(?:not|never|no|none|nothing|neither|nor|without)\b")
        trigger = re.compile(r"(?i)\b(?:accepted|passing|green|clean)\b")
        for path in ALL_NEW_FILES:
            with self.subTest(path=path.name):
                body = path.read_text(encoding="utf-8")
                violations = [
                    sentence.strip()
                    for sentence in re.split(r"(?<=[.!?])\s+|\n\n+", body)
                    if grants.search(sentence)
                    and trigger.search(sentence)
                    and not negation.search(sentence)
                ]
                self.assertEqual(
                    violations, [], f"affirmative authorization grant in {path.name}: {violations}"
                )

    def test_skill_never_runs_git_or_forge_mutations(self) -> None:
        text = self.skill_text
        for command in ("git add", "git commit", "git push", "gh pr create", "gh pr edit", "gh pr merge"):
            with self.subTest(command=command):
                self.assertIn(command, text)
        self.assertNotRegex(
            text,
            re.compile(
                r"(?im)\b(?:run|execute)\s+`?(?:git\s+(?:add|commit|push|rebase|merge)\b|"
                r"gh\s+pr\s+(?:create|edit|merge)\b|deploy\b)"
            ),
        )

    def test_hard_rules_present(self) -> None:
        """The rules that make an ADR an ADR. Each is load-bearing doctrine, not prose."""
        text = self.skill_text
        checks = {
            "two options": re.compile(r"(?i)at least two|two genuinely considered"),
            "negative consequence": re.compile(r"(?i)negative consequence"),
            "immutable after accept": re.compile(r"(?i)immutab\w+ after accept"),
            "supersede not edit": re.compile(r"(?i)supersede,? never edit|supersede instead"),
            "one decision per file": re.compile(r"(?i)one decision per file"),
            "no changelog drift": re.compile(r"(?i)changelog"),
            "reversal condition": re.compile(r"(?i)reversal condition"),
            "confirmation names something real": re.compile(r"(?i)confirmation"),
            "significance gate": re.compile(r"(?i)significance gate"),
        }
        for name, pattern in checks.items():
            with self.subTest(rule=name):
                self.assertRegex(text, pattern)

    def test_status_vocabulary_is_closed_and_divergence_disclosed(self) -> None:
        """The house format closes the status enum where upstream leaves it free text.
        Both facts must be stated, so a reader checking upstream is not surprised."""
        states = REFERENCES["lifecycle-states"].read_text(encoding="utf-8")
        for status in ("proposed", "accepted", "rejected", "deprecated", "superseded by"):
            with self.subTest(status=status):
                self.assertIn(status, states)
        template = REFERENCES["house-template"].read_text(encoding="utf-8")
        self.assertRegex(template, re.compile(r"(?i)free[- ]text"))

    def test_supersession_ordering_rule_present(self) -> None:
        """The replacement reaches accepted BEFORE the old status flips — the window where
        neither record is in force is the failure this rule prevents. The crisp rule lives in
        the skill body; the failure it prevents is spelled out in the reference."""
        self.assertRegex(
            self.skill_text,
            re.compile(r"(?is)replacement reaches\s+`?accepted`?\s+\*?before\*?[^.]{0,120}flip"),
        )
        states = REFERENCES["lifecycle-states"].read_text(encoding="utf-8")
        self.assertRegex(states, re.compile(r"(?i)neither\*?\s*record"))
        self.assertRegex(states, re.compile(r"(?i)order matters"))

    def test_only_accepted_records_are_constraints(self) -> None:
        states = REFERENCES["lifecycle-states"].read_text(encoding="utf-8")
        self.assertRegex(states, re.compile(r"(?i)only\s+`?accepted`?\s+records\s+are\s+constraints"))

    def test_evidence_reference_states_non_claims(self) -> None:
        evidence = REFERENCES["adr-as-evidence"].read_text(encoding="utf-8")
        self.assertRegex(evidence, re.compile(r"(?i)non-?claims"))
        # The two most-assumed inversions must be denied explicitly.
        self.assertRegex(
            evidence,
            re.compile(r"(?is)does not authorize the change that implements it"),
        )
        self.assertRegex(
            evidence,
            re.compile(r"(?is)does not retroactively make"),
        )


class ReferenceInsteadVerdictTests(unittest.TestCase):
    """The four gate-3/gate-2 verdicts: capability lands as a reference under the skill that
    already owns the ground, with a pointer from that skill's own body."""

    def test_reference_files_exist_and_are_pointed_at(self) -> None:
        for name, (reference, owner) in REFERENCE_VERDICTS.items():
            with self.subTest(capability=name):
                self.assertTrue(reference.is_file(), f"missing {reference}")
                owner_text = owner.read_text(encoding="utf-8")
                self.assertIn(f"references/{reference.name}", owner_text)

    def test_no_competing_top_level_skill_was_created(self) -> None:
        """Each of these was specced as its own skill and demoted by the four-gate test.
        Promoting one later means deleting an assertion here on purpose."""
        for slug in (
            "conventional-commits",
            "technical-writing-clarity",
            "asd-ste100",
            "mermaid-diagrams",
            "autoresearch-lab",
            "research-claim-ledger",
        ):
            with self.subTest(slug=slug):
                self.assertFalse(
                    (ROOT / "skills" / slug).exists(),
                    f"skills/{slug}/ exists: promotion needs the >=2-of-5 argument recorded",
                )

    def test_conventional_commits_stays_subordinate_to_repo_convention(self) -> None:
        text = CONVENTIONAL_COMMITS.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)fallback"))
        self.assertRegex(text, re.compile(r"(?i)repository'?s own convention wins|convention\s+wins"))
        # Flexible whitespace: the prose wraps, so a literal space would miss a line break.
        self.assertRegex(text, re.compile(r"(?i)never\s+converts\s+that\s+format\s+into\s+a\s+mandate"))
        self.assertRegex(text, re.compile(r"(?i)local dialect"))
        # Attribution is decided by the policy file, not here.
        self.assertIn("attribution-policy.md", text)

    def test_conventional_commits_records_linter_divergence(self) -> None:
        """A message can be spec-conformant and still fail a lint run. The 16 rules and the
        divergence table both have to be present for the reference to be usable alone."""
        text = CONVENTIONAL_COMMITS.read_text(encoding="utf-8")
        self.assertIn("BREAKING CHANGE", text)
        self.assertRegex(text, re.compile(r"(?i)uppercase"))
        self.assertRegex(text, re.compile(r"(?i)trailing period"))
        # The local-dialect trap: an unextended preset rejects this repo's own `merge:`.
        self.assertIn("merge:", text)

    def test_writing_clarity_makes_no_compliance_claim(self) -> None:
        """The standard is trademarked and its dictionary is licensed. The reference may
        restate public rule shapes only, and must never claim compliance."""
        text = WRITING_CLARITY.read_text(encoding="utf-8")
        # The forbidden phrases must appear ONLY inside the prohibition that names them, which
        # is quoted. So: every occurrence has to be quote-wrapped. A bare, unquoted
        # "STE compliant" would be the file asserting compliance rather than forbidding it.
        claim_phrase = re.compile(
            r"(?i)\b(?:STE|ASD-STE100|Simplified Technical English)[- ]?"
            r"(?:compliant|certified|conformant)\b"
        )
        for match in claim_phrase.finditer(text):
            with self.subTest(phrase=match.group(0)):
                before = text[max(0, match.start() - 2):match.start()]
                after = text[match.end():match.end() + 2]
                self.assertTrue(
                    ('"' in before or "“" in before) and ('"' in after or "”" in after),
                    f"unquoted compliance claim: {text[match.start()-60:match.end()+60]!r}",
                )
        # And the prohibition itself must be present, not merely implied by absence.
        self.assertRegex(text, re.compile(r"(?i)never claim compliance"))
        self.assertRegex(text, re.compile(r"(?i)trademark"))
        self.assertRegex(text, re.compile(r"(?i)does not reproduce"))
        self.assertRegex(text, re.compile(r"(?i)endorse"))
        # No dictionary reconstruction, in any form.
        self.assertFalse((WRITING_CLARITY.parent / "dictionary.md").exists())
        self.assertRegex(text, re.compile(r"(?i)countable"))
        self.assertRegex(text, re.compile(r"(?i)judgment"))

    def test_writing_clarity_preserves_evidence_class(self) -> None:
        """A clarity edit must never strengthen a claim. This is where sentence mechanics
        meets change-writing's evidence ladder, and the ladder wins."""
        text = WRITING_CLARITY.read_text(encoding="utf-8")
        self.assertIn("evidence-order.md", text)
        self.assertRegex(text, re.compile(r"(?is)never let a rewrite change a claim'?s strength"))

    def test_mermaid_authoring_does_not_claim_a_renderer(self) -> None:
        """Authoring only. The rendering pipeline is a separate concern and no renderer is
        pinned by this file."""
        text = MERMAID_AUTHORING.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)authoring"))
        self.assertRegex(text, re.compile(r"(?i)nothing here pins a renderer|no renderer"))
        self.assertRegex(text, re.compile(r"(?i)promotion trigger"))

    def test_mermaid_authoring_does_not_teach_refuted_traps(self) -> None:
        """Executed against mermaid-cli 11.16.0: `click` and `default` as node IDs parse
        cleanly, and an o-initial EDGE LABEL is harmless. Teaching them as traps would send
        readers to rename working identifiers."""
        text = MERMAID_AUTHORING.read_text(encoding="utf-8")
        # Both appear only in the do-not-teach section, which must be present.
        self.assertRegex(text, re.compile(r"(?i)do NOT reproduce|do not teach these", re.I))
        for refuted in ("click", "default"):
            with self.subTest(refuted=refuted):
                self.assertRegex(
                    text,
                    re.compile(rf"(?is)not reproduce.{{0,600}}`{refuted}`"),
                    f"`{refuted}` must be listed as refuted, never as a reserved-word trap",
                )
        # The real o/x trap is scoped to a node ID after `---`, not to label text.
        self.assertRegex(text, re.compile(r"(?is)node\s+ID\b.{0,80}`---`|`---`.{0,120}node"))

    def test_mermaid_authoring_separates_loud_from_silent_traps(self) -> None:
        """The exit-0 traps are the dangerous ones; the file must not blend them into the
        exit-1 list, or a reader will trust the exit code."""
        text = MERMAID_AUTHORING.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)exit 1"))
        self.assertRegex(text, re.compile(r"(?i)succeed and draw the wrong thing|exit code 0 tells you nothing"))
        self.assertIn("circleEnd", text)

    def test_claim_obligations_documents_the_substring_defect(self) -> None:
        """The reference exists to fix a live defect. It must name the defect concretely,
        including that the gate reads a field the constrained party writes."""
        text = CLAIM_OBLIGATIONS.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)substring"))
        self.assertRegex(text, re.compile(r"(?i)free[- ]text"))
        self.assertRegex(text, re.compile(r"(?is)writable by the party it constrains|author"))
        # The independence rule is a field comparison, not a promise.
        self.assertRegex(text, re.compile(r"author_role\s*!=\s*claim\.owner_agent|review\.author_role"))
        self.assertRegex(text, re.compile(r"(?i)revision"))
        self.assertRegex(text, re.compile(r"(?i)fails? closed"))

    def test_claim_obligations_states_built_versus_designed(self) -> None:
        """The installer's semantics ship today; the obligation block does not. A reader
        must not mistake the design for available behaviour."""
        text = CLAIM_OBLIGATIONS.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)designed"))
        self.assertRegex(text, re.compile(r"(?i)shipped today"))
        self.assertRegex(text, re.compile(r"(?i)not built"))
        # Ownership/manifest semantics of the landed installer must not be contradicted.
        self.assertRegex(text, re.compile(r"(?i)ownership"))
        self.assertRegex(text, re.compile(r"(?i)nothing in this design broadens ownership"))

    def test_bounded_lab_loop_keeps_the_authority_boundary(self) -> None:
        text = BOUNDED_LAB_LOOP.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)self-improving is not self-authorizing"))
        self.assertRegex(text, re.compile(r"(?i)harness"))
        self.assertRegex(text, re.compile(r"(?i)void"))
        self.assertRegex(text, re.compile(r"(?i)append-only"))
        # Unattended scheduling is refused, with the reason.
        self.assertRegex(text, re.compile(r"(?i)unattended"))
        self.assertRegex(text, re.compile(r"(?i)not authorized"))
        # Negatives are retained: the ledger keeps discarded trials.
        self.assertRegex(text, re.compile(r"(?is)keep the trial line|negatives? (?:are )?retained"))

    def test_bounded_lab_loop_names_the_metric_ratchet_defect(self) -> None:
        """A pure improvement ratchet hill-climbs into a local maximum. The fixes
        (exploration reserve, stall rule) are the reason this is worth writing down."""
        text = BOUNDED_LAB_LOOP.read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"(?i)exploration prob"))
        self.assertRegex(text, re.compile(r"(?i)stall rule"))
        self.assertRegex(text, re.compile(r"(?i)local maximum"))
        self.assertRegex(text, re.compile(r"(?i)pre-?register"))


class NewSurfaceHygieneTests(unittest.TestCase):
    """Repo-wide tripwires, applied to every file this change adds."""

    def test_no_host_specific_paths_or_credentials(self) -> None:
        for path in ALL_NEW_FILES:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, re.compile(r"/home/|/Users/|C:\\Users"))
                self.assertNotRegex(
                    text,
                    re.compile(r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA|OPENSSH) PRIVATE KEY"),
                )
                # The validator's own secret/hostname pattern.
                self.assertNotRegex(text, re.compile(r"amazon\.com/[a-z]|\.a2z\.com|aws\.dev/"))

    def test_references_are_self_contained(self) -> None:
        """Admission floor: a reader holding only one reference must be able to act, so each
        says so and none requires the parent SKILL.md to be open."""
        for name, path in REFERENCES.items():
            with self.subTest(reference=name):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text, re.compile(r"(?i)self-contained"))


if __name__ == "__main__":
    unittest.main()
