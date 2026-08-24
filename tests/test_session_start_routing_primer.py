"""Behavior of the shipped SessionStart routing primer, run as the real `sh` script.

Two properties carry the plane's additive identity and both are asserted as byte counts, not
intent: an activated repository gets the routing card on stdout at exit 0, and a non-activated
repository gets ZERO bytes of stdout at exit 0 — empty stdout on exit 0 injects nothing into a
session, so silence is structural. The freshness test makes the hand-maintained card executable:
every `-> <skill>` target it names must exist under skills/, with a mutation positive control
proving the extraction bites (the verify-tests-by-mutation lesson).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
HOOK = ROOT / "hooks" / "session-start-routing-primer.sh"
ACTIVATION_MARKER = "<!-- agentic-sdlc:start -->"
CARD_PATTERN = re.compile(r"<<'ROUTING_CARD'\n(.*?)\nROUTING_CARD\n", re.DOTALL)
TARGET_PATTERN = re.compile(r"->\s*([a-z][a-z0-9]*(?:-[a-z0-9]+)*)")


def run_hook(project_dir: Path | None, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    if project_dir is not None:
        environment["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["sh", str(HOOK)],
        check=False,
        capture_output=True,
        cwd=cwd,
        env=environment,
        timeout=30,
    )


def card_text() -> str:
    match = CARD_PATTERN.search(HOOK.read_text(encoding="utf-8"))
    assert match, "the hook must emit its card through one quoted ROUTING_CARD heredoc"
    return match.group(1)


def missing_targets(card: str) -> list[str]:
    targets = TARGET_PATTERN.findall(card)
    assert len(targets) >= 10, f"card target extraction found too few rows to be real: {targets}"
    return [target for target in targets if not (ROOT / "skills" / target / "SKILL.md").is_file()]


class RoutingPrimerBehaviorTests(unittest.TestCase):
    maxDiff = None

    def activated_fixture(self, root: Path) -> Path:
        repo = root / "repo"
        (repo / ".seeds").mkdir(parents=True)
        (repo / ".seeds" / "issues.jsonl").write_text('{"id":"x"}\n', encoding="utf-8")
        (repo / "AGENTS.md").write_text(f"{ACTIVATION_MARKER}\nrouter\n<!-- agentic-sdlc:end -->\n", encoding="utf-8")
        return repo

    def test_an_activated_repository_gets_the_card_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.activated_fixture(Path(temp))
            completed = run_hook(repo)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertIn(b"agentic-sdlc routing primer", completed.stdout)
        self.assertLessEqual(len(completed.stdout), 2048, "the emitted card exceeds its 2 KiB budget")
        self.assertGreater(len(completed.stdout), 0)

    def test_a_missing_queue_is_zero_bytes_at_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.activated_fixture(Path(temp))
            (repo / ".seeds" / "issues.jsonl").unlink()
            completed = run_hook(repo)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b"")
        self.assertEqual(completed.stderr, b"")

    def test_a_missing_activation_marker_is_zero_bytes_at_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.activated_fixture(Path(temp))
            (repo / "AGENTS.md").write_text("plain template, no marker\n", encoding="utf-8")
            completed = run_hook(repo)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b"")

        # A missing AGENTS.md degrades to the same silence, never to a grep error on stderr.
        with tempfile.TemporaryDirectory() as temp:
            repo = self.activated_fixture(Path(temp))
            (repo / "AGENTS.md").unlink()
            completed = run_hook(repo)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b"")
        self.assertEqual(completed.stderr, b"")

    def test_a_symlinked_queue_is_zero_bytes_at_exit_zero(self) -> None:
        """`.seeds/issues.jsonl` must be a regular non-symlink file; a link is not the surface
        the conductor-write launcher creates, so it does not activate the primer."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.activated_fixture(root)
            queue = repo / ".seeds" / "issues.jsonl"
            queue.unlink()
            (root / "elsewhere.jsonl").write_text('{"id":"x"}\n', encoding="utf-8")
            queue.symlink_to(root / "elsewhere.jsonl")
            completed = run_hook(repo)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b"")

    def test_the_cwd_fallback_serves_a_session_without_the_env_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.activated_fixture(Path(temp))
            completed = run_hook(None, cwd=repo)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(b"agentic-sdlc routing primer", completed.stdout)


class RoutingCardShapeTests(unittest.TestCase):
    def test_the_shipped_file_and_card_fit_their_byte_budgets(self) -> None:
        self.assertLessEqual(len(HOOK.read_bytes()), 4096)
        self.assertLessEqual(len(card_text().encode("utf-8")), 2048)

    def test_the_card_is_static_reviewed_bytes_with_no_interpolation(self) -> None:
        """The injection posture, pinned executably: the heredoc delimiter is quoted and the card
        carries no shell expansion, so no repository content can reach the emitted context."""
        text = HOOK.read_text(encoding="utf-8")
        self.assertIn("<<'ROUTING_CARD'", text)
        card = card_text()
        self.assertNotIn("$", card)
        self.assertNotIn("`", card)

    def test_every_routing_target_names_a_shipped_skill(self) -> None:
        self.assertEqual(missing_targets(card_text()), [])

    def test_the_freshness_check_bites_on_a_renamed_skill(self) -> None:
        """Mutation positive control: the assertion above must be able to fail, or the card can
        rot silently when a skill is renamed (the prose-that-asserts lesson, made executable)."""
        card = card_text()
        mutated = card.replace("change-writing", "no-such-skill-anywhere", 1)
        self.assertNotEqual(mutated, card, "the mutation target must be present in the card")
        self.assertEqual(missing_targets(mutated), ["no-such-skill-anywhere"])

    def test_the_card_names_the_flagship_router_rows(self) -> None:
        card = card_text()
        for required in ("model-tier-rightsizing", "change-writing", "agentic-sdlc", "reviewing-overengineering"):
            self.assertIn(f"-> {required}", card)


if __name__ == "__main__":
    unittest.main()
