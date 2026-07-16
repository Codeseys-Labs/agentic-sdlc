from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]

# Single place a pre-vs-post-rename landing order would touch for the flagship
# routing hook. The skill directory itself is `change-writing`, independent of
# the flagship rename.
FLAGSHIP = ROOT / "skills" / "agentic-sdlc" / "SKILL.md"

SKILL = ROOT / "skills" / "change-writing" / "SKILL.md"
REFERENCES = {
    "commit": SKILL.parent / "references" / "commit.md",
    "pull-request": SKILL.parent / "references" / "pull-request.md",
    "squash": SKILL.parent / "references" / "squash.md",
    "draft-review": SKILL.parent / "references" / "draft-review.md",
    "attribution-policy": SKILL.parent / "references" / "attribution-policy.md",
    "evidence-order": SKILL.parent / "references" / "evidence-order.md",
}
FIXTURES = ROOT / "tests" / "fixtures" / "change-writing"

STACKED = ROOT / "skills" / "stacked-prs" / "SKILL.md"
STACKED_GH = ROOT / "skills" / "stacked-prs-gh-cli" / "SKILL.md"


# --- Attribution detector (built from references/attribution-policy.md deny tokens) ---
# Matches MODEL/AGENT attribution but not a real human Co-Authored-By trailer.
ATTRIBUTION_DENY = [
    # Co-Authored-By naming a model/agent/provider (not a human).
    re.compile(
        r"(?im)^\s*Co-Authored-By:\s*"
        r"(?:Claude|Codex|GPT|ChatGPT|Opus|Sonnet|Haiku|Gemini|Copilot|Devin|Cursor|"
        r"Anthropic|OpenAI|.*\bBot\b)"
    ),
    # Bot no-reply identities used as a co-author (human users.noreply.github.com is fine).
    re.compile(r"(?im)^\s*Co-Authored-By:.*<[^>]*noreply@(?:anthropic|openai)\.com[^>]*>"),
    # Generated-with footers, with or without the robot badge glyph.
    re.compile(r"(?im)(?:\U0001F916\s*)?Generated with\b"),
    # Model/AI authorship anywhere in a line (NOT only as a trailing footer), so an
    # in-sentence "written by an AI assistant" is caught, not just a footer form.
    re.compile(
        r"(?i)\b(?:Written|Authored|Generated|Created|Produced) by\s+"
        r"(?:(?:an?\s+)?(?:AI|artificial intelligence)\b"
        r"|Claude|Codex|GPT|ChatGPT|Opus|Sonnet|Haiku|Gemini|Copilot)"
    ),
    # Agent/model marketing badge (markdown image whose alt text names a model/AI).
    re.compile(
        r"(?im)!\[[^\]]*(?:Claude|Codex|GPT|Copilot|Gemini|Opus|Sonnet|\bAI\b)[^\]]*\]\([^)]*\)"
    ),
    # Agent/model marketing badge (HTML <img> whose alt text names a model/AI),
    # scoped to the alt value so a diagram whose src filename happens to contain a
    # model name is not flagged.
    re.compile(
        r"(?is)<img\b[^>]*\balt\s*=\s*[\"'][^\"']*"
        r"(?:Claude|Codex|GPT|Copilot|Gemini|Opus|Sonnet|\bAI\b)[^\"']*[\"']"
    ),
    # A standalone robot glyph leading a line is a footer/badge — distinct from a
    # 🤖 emoji mentioned mid-sentence in prose (which does not lead a line).
    re.compile(r"(?m)^\s*\U0001F916"),
]


def attribution_detected(text: str) -> bool:
    return any(pattern.search(text) for pattern in ATTRIBUTION_DENY)


# --- Unsupported-claim heuristic (omit-or-placeholder rule made testable) ---
CLAIM_PATTERN = re.compile(
    r"(?i)\ball tests? pass|\b\d+\s+tests?\s+pass|passes all tests|"
    r"\b(?:fixes|closes|resolves)\s+#\d+|coverage\s+(?:is\s+)?\d+%"
)
# A code fence, an inline backticked command, or a concrete TODO placeholder.
EVIDENCE_MARKER = re.compile(r"```|`[^`]+`|TODO:")


def unsupported_claim(text: str) -> bool:
    return bool(CLAIM_PATTERN.search(text)) and not EVIDENCE_MARKER.search(text)


# --- Frontmatter parsing mirroring scripts/validate_bundle.py:319-342 ---
def _frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return match.group(1) if match else ""


def _metadata_value(metadata: str, name: str) -> str:
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


class ChangeWritingSkillTests(unittest.TestCase):
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
        self.assertEqual(_metadata_value(metadata, "name"), "change-writing")
        description = _metadata_value(metadata, "description")
        self.assertTrue(description, "description must be present")
        self.assertLessEqual(len(description), 1024)

    def test_authority_boundary_declared(self) -> None:
        text = self.skill_text
        # Output-only declaration and an explicit forbidden-operations list.
        self.assertRegex(text, re.compile(r"output[- ]only", re.I))
        for command in ("git add", "git commit", "git push", "gh pr create", "gh pr edit", "gh pr merge", "git merge"):
            with self.subTest(command=command):
                self.assertIn(command, text)
        # The skill must never instruct itself to RUN a mutation (imperative run/execute).
        self.assertNotRegex(
            text,
            re.compile(
                r"(?im)\b(?:run|execute)\s+`?(?:git\s+(?:add|commit|push|rebase|merge)\b|"
                r"gh\s+pr\s+(?:create|edit|merge)\b|deploy\b)"
            ),
        )

    def test_attribution_default_deny_documented(self) -> None:
        text = REFERENCES["attribution-policy"].read_text(encoding="utf-8")
        for token in ("Co-Authored-By: Claude", "Co-Authored-By: Codex", "Generated with"):
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertIn("\U0001F916", text)  # robot badge glyph appears as a deny example
        self.assertRegex(text, re.compile(r"unless.*explicitly request", re.I | re.S))
        # Human co-author carve-out.
        self.assertRegex(text, re.compile(r"human", re.I))
        self.assertRegex(text, re.compile(r"co-?author", re.I))

    def test_forbidden_fixtures_are_detected(self) -> None:
        forbidden = sorted((FIXTURES / "forbidden").glob("*"))
        self.assertTrue(forbidden, "forbidden fixtures missing")
        attribution_fixtures = [p for p in forbidden if p.name != "invented-claim.md"]
        self.assertGreaterEqual(len(attribution_fixtures), 5)
        for path in attribution_fixtures:
            with self.subTest(fixture=path.name):
                # Direction 1: a weakened detector that misses any of these FAILS here.
                self.assertTrue(
                    attribution_detected(path.read_text(encoding="utf-8")),
                    f"detector missed forbidden attribution in {path.name}",
                )

    def test_clean_fixtures_pass(self) -> None:
        clean = sorted((FIXTURES / "clean").glob("*"))
        self.assertTrue(clean, "clean fixtures missing")
        for path in clean:
            with self.subTest(fixture=path.name):
                # Direction 2: an over-broad detector that trips a clean file FAILS here,
                # including the legitimate human Co-Authored-By trailer.
                self.assertFalse(
                    attribution_detected(path.read_text(encoding="utf-8")),
                    f"detector false-positive on clean {path.name}",
                )
        self.assertTrue((FIXTURES / "clean" / "commit-human-coauthor.txt").is_file())

    def test_invented_claim_fixture_flagged(self) -> None:
        invented = (FIXTURES / "forbidden" / "invented-claim.md").read_text(encoding="utf-8")
        self.assertTrue(unsupported_claim(invented), "unsupported-claim heuristic missed the invented claim")
        # Carve-out: a claim backed by an evidence marker is not flagged.
        pr_body = (FIXTURES / "clean" / "pr-body.md").read_text(encoding="utf-8")
        self.assertFalse(unsupported_claim(pr_body), "evidence-backed verification wrongly flagged")

    def test_evidence_order_and_merge_base(self) -> None:
        evidence = REFERENCES["evidence-order"].read_text(encoding="utf-8")
        # Six-step ladder present.
        self.assertGreaterEqual(len(re.findall(r"(?m)^\s*\d+\.", evidence)), 6)
        self.assertRegex(evidence, re.compile(r"omit|TODO:", re.I))
        combined = self.skill_text + evidence
        self.assertRegex(combined, re.compile(r"evidence", re.I))
        pr = REFERENCES["pull-request"].read_text(encoding="utf-8")
        self.assertRegex(pr, re.compile(r"merge[- ]base", re.I))
        self.assertRegex(pr, re.compile(r"not\s+(?:the\s+)?HEAD diff", re.I))

    def test_repo_policy_wins_over_conventional_commits(self) -> None:
        commit = REFERENCES["commit"].read_text(encoding="utf-8")
        combined = self.skill_text + commit
        self.assertRegex(combined, re.compile(r"Conventional Commits", re.I))
        self.assertRegex(combined, re.compile(r"fallback", re.I))
        self.assertRegex(combined, re.compile(r"rep(?:ository|o)[- ].*(?:win|beat|precede|override)", re.I | re.S))

    def test_routing_hooks_present(self) -> None:
        flagship = FLAGSHIP.read_text(encoding="utf-8")
        stacked = STACKED.read_text(encoding="utf-8")
        stacked_gh = STACKED_GH.read_text(encoding="utf-8")
        for name, text in (("flagship", flagship), ("stacked-prs", stacked), ("stacked-prs-gh-cli", stacked_gh)):
            with self.subTest(surface=name):
                self.assertIn("change-writing", text)
        # Routing surfaces must not re-declare a PR/commit format template block.
        self.assertNotRegex(flagship, re.compile(r"(?m)^##+\s+Verification\b"))
        # Symmetric split: change-writing must not carry stacked-PR topology ops.
        change_writing_text = self.skill_text
        for path in REFERENCES.values():
            change_writing_text += path.read_text(encoding="utf-8")
        self.assertNotRegex(change_writing_text, re.compile(r"--force-with-lease"))
        self.assertNotRegex(change_writing_text, re.compile(r"git rebase --onto"))
        self.assertNotRegex(change_writing_text, re.compile(r"(?i)restack"))
        self.assertNotRegex(change_writing_text, re.compile(r"saved-remote-oid"))
        self.assertNotRegex(change_writing_text, re.compile(r"gh pr (?:create|edit|merge)\b[^\n]*\s--"))


if __name__ == "__main__":
    unittest.main()
