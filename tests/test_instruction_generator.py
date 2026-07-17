from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import instruction_generator as gen


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "instruction_generator.py"
MARKER_START = "<!-- agentic-sdlc:start -->"
MARKER_END = "<!-- agentic-sdlc:end -->"


def base_manifest() -> dict:
    return {
        "schema": "agentic-sdlc/instruction-manifest@1",
        "marker": {"start": MARKER_START, "end": MARKER_END},
        "doctrine_pointer": "skills/agentic-sdlc/SKILL.md",
        "root_agents": {
            "path": "AGENTS.md",
            "sections": [
                {"key": "intent", "body": "Project intent for the wave."},
                {"key": "gate", "body": "Run `mise run check` before any commit."},
                {"key": "substrate", "body": "Git-worktree waves only."},
                {"key": "seeds", "body": "Seeds(<target>, prime|ready|blocked)."},
                {"key": "doctrine", "body": "See skills/agentic-sdlc/SKILL.md for the doctrine."},
            ],
        },
        "root_claude": {
            "path": "CLAUDE.md",
            "import": "@AGENTS.md",
            "claude_routing": ["/sdlc-init", "/sdlc-frame", "/sdlc-wave", "/sdlc-mission"],
        },
        "subtrees": [],
        "claude_rules": [],
    }


def entry(result: dict, path: str) -> dict:
    matches = [item for item in result["files"] if item["path"] == path]
    if not matches:
        raise AssertionError(f"no plan entry for {path}: {result['files']}")
    return matches[0]


def count_markers(text: str) -> tuple[int, int]:
    return text.count(MARKER_START), text.count(MARKER_END)


class InstructionGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # A real doctrine file so pointer/no-duplication checks have a target to read.
        doctrine = self.root / "skills" / "agentic-sdlc" / "SKILL.md"
        doctrine.parent.mkdir(parents=True)
        doctrine.write_text(
            "---\nname: agentic-sdlc\n---\n\n"
            "# Agentic SDLC doctrine\n\n"
            "The conductor is the sole queue writer for Seeds.\n"
            "Workers are read-only and never mutate the queue directly.\n"
            "Every wave runs on Git worktrees with a pinned mise gate stack.\n"
            "The critique team files advisory findings, not authority.\n",
            encoding="utf-8",
        )
        self.addCleanup(self._tmp.cleanup)

    # --- A3-T01 -----------------------------------------------------------
    def test_a3_t01_empty_tree_creates_marked_root_files(self) -> None:
        result = gen.generate(base_manifest(), self.root, apply=True)
        self.assertTrue(result["ok"], result["conflicts"])
        agents = self.root / "AGENTS.md"
        claude = self.root / "CLAUDE.md"
        self.assertTrue(agents.is_file())
        self.assertTrue(claude.is_file())
        self.assertEqual(count_markers(agents.read_text(encoding="utf-8")), (1, 1))
        self.assertEqual(count_markers(claude.read_text(encoding="utf-8")), (1, 1))
        self.assertEqual(entry(result, "AGENTS.md")["action"], "create")
        self.assertEqual(entry(result, "CLAUDE.md")["action"], "create")

    # --- A3-T02 -----------------------------------------------------------
    def test_a3_t02_claude_is_thin_routing_only(self) -> None:
        gen.generate(base_manifest(), self.root, apply=True)
        text = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("@AGENTS.md\n"))
        self.assertIn("/sdlc-init", text)
        # Doctrine body must not be copied into the thin CLAUDE block.
        self.assertNotIn("The conductor is the sole queue writer for Seeds.", text)

    # --- A3-T03 -----------------------------------------------------------
    def test_a3_t03_foreign_preamble_preserved_on_merge(self) -> None:
        agents = self.root / "AGENTS.md"
        foreign = "# Team hand-authored policy\n\nDo not delete this paragraph.\n"
        agents.write_text(foreign, encoding="utf-8")
        result = gen.generate(base_manifest(), self.root, apply=True)
        self.assertEqual(entry(result, "AGENTS.md")["action"], "merge")
        text = agents.read_text(encoding="utf-8")
        self.assertIn(foreign.strip(), text)
        self.assertEqual(count_markers(text), (1, 1))

    # --- A3-T04 -----------------------------------------------------------
    def test_a3_t04_correct_block_is_adopted_noop(self) -> None:
        gen.generate(base_manifest(), self.root, apply=True)
        before = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        result = gen.generate(base_manifest(), self.root, apply=True)
        after = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(entry(result, "AGENTS.md")["action"], "adopt")
        self.assertEqual(before, after)

    # --- A3-T05 -----------------------------------------------------------
    def test_a3_t05_duplicate_start_markers_refused(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text(
            f"{MARKER_START}\nold\n{MARKER_END}\n{MARKER_START}\nsecond\n{MARKER_END}\n",
            encoding="utf-8",
        )
        original = agents.read_text(encoding="utf-8")
        result = gen.generate(base_manifest(), self.root, apply=True)
        item = entry(result, "AGENTS.md")
        self.assertEqual(item["action"], "refuse")
        self.assertEqual(item["conflict"], "duplicate-marker")
        self.assertFalse(result["ok"])
        self.assertEqual(agents.read_text(encoding="utf-8"), original)

    # --- A3-T06 -----------------------------------------------------------
    def test_a3_t06_start_without_end_refused(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text(f"{MARKER_START}\nno closing marker here\n", encoding="utf-8")
        original = agents.read_text(encoding="utf-8")
        result = gen.generate(base_manifest(), self.root, apply=True)
        item = entry(result, "AGENTS.md")
        self.assertEqual(item["action"], "refuse")
        self.assertEqual(item["conflict"], "malformed-marker")
        self.assertEqual(agents.read_text(encoding="utf-8"), original)

    # --- A3-T07 -----------------------------------------------------------
    def test_a3_t07_end_before_start_refused(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text(f"{MARKER_END}\nbody\n{MARKER_START}\n", encoding="utf-8")
        original = agents.read_text(encoding="utf-8")
        result = gen.generate(base_manifest(), self.root, apply=True)
        item = entry(result, "AGENTS.md")
        self.assertEqual(item["action"], "refuse")
        self.assertEqual(item["conflict"], "malformed-marker")
        self.assertEqual(agents.read_text(encoding="utf-8"), original)

    # --- A3-T08 -----------------------------------------------------------
    def test_a3_t08_subtree_created_with_pointer_no_doctrine_body(self) -> None:
        manifest = base_manifest()
        manifest["subtrees"] = [
            {
                "path": "services/api/AGENTS.md",
                "inherits": "root",
                "sections": [{"key": "local-gate", "body": "Run the api test suite locally."}],
            }
        ]
        result = gen.generate(manifest, self.root, apply=True)
        self.assertTrue(result["ok"], result["conflicts"])
        sub = self.root / "services" / "api" / "AGENTS.md"
        self.assertTrue(sub.is_file())
        text = sub.read_text(encoding="utf-8")
        self.assertIn("skills/agentic-sdlc/SKILL.md", text)
        self.assertIn("Run the api test suite locally.", text)
        self.assertNotIn("The conductor is the sole queue writer for Seeds.", text)
        self.assertEqual(count_markers(text), (1, 1))

    # --- A3-T09 -----------------------------------------------------------
    def test_a3_t09_claude_rule_created_single_pair(self) -> None:
        manifest = base_manifest()
        manifest["claude_rules"] = [
            {"path": ".claude/rules/worktrees.md", "sections": [{"key": "rule", "body": "One worktree per worker."}]}
        ]
        gen.generate(manifest, self.root, apply=True)
        rule = self.root / ".claude" / "rules" / "worktrees.md"
        self.assertTrue(rule.is_file())
        self.assertEqual(count_markers(rule.read_text(encoding="utf-8")), (1, 1))

    # --- A3-T10 -----------------------------------------------------------
    def test_a3_t10_foreign_rule_untouched(self) -> None:
        manifest = base_manifest()
        manifest["claude_rules"] = [
            {"path": ".claude/rules/worktrees.md", "sections": [{"key": "rule", "body": "One worktree per worker."}]}
        ]
        other = self.root / ".claude" / "rules" / "other.md"
        other.parent.mkdir(parents=True)
        other.write_text("hand-authored, not in manifest\n", encoding="utf-8")
        gen.generate(manifest, self.root, apply=True)
        self.assertEqual(other.read_text(encoding="utf-8"), "hand-authored, not in manifest\n")

    # --- A3-T11 -----------------------------------------------------------
    def test_a3_t11_inlined_doctrine_fails_validation(self) -> None:
        manifest = base_manifest()
        manifest["root_agents"]["sections"].append(
            {
                "key": "doctrine-copy",
                "body": (
                    "The conductor is the sole queue writer for Seeds.\n"
                    "Workers are read-only and never mutate the queue directly.\n"
                    "Every wave runs on Git worktrees with a pinned mise gate stack.\n"
                ),
            }
        )
        result = gen.generate(manifest, self.root, apply=True)
        item = entry(result, "AGENTS.md")
        self.assertEqual(item["action"], "refuse")
        self.assertEqual(item["conflict"], "doctrine-duplication")
        self.assertFalse((self.root / "AGENTS.md").exists())

    # --- A3-T12 -----------------------------------------------------------
    def test_a3_t12_plan_writes_nothing_returns_diffs(self) -> None:
        result = gen.generate(base_manifest(), self.root, apply=False)
        self.assertEqual(result["mode"], "plan")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        for path in ("AGENTS.md", "CLAUDE.md"):
            self.assertTrue(entry(result, path)["unified_diff"])

    # --- A3-T13 / A3-T17 --------------------------------------------------
    def test_a3_t13_rerun_is_byte_identical_all_adopt(self) -> None:
        gen.generate(base_manifest(), self.root, apply=True)
        first = {p: (self.root / p).read_text(encoding="utf-8") for p in ("AGENTS.md", "CLAUDE.md")}
        result = gen.generate(base_manifest(), self.root, apply=True)
        second = {p: (self.root / p).read_text(encoding="utf-8") for p in ("AGENTS.md", "CLAUDE.md")}
        self.assertEqual(first, second)
        self.assertEqual(entry(result, "AGENTS.md")["action"], "adopt")
        self.assertEqual(entry(result, "CLAUDE.md")["action"], "adopt")

    def test_a3_t17_render_is_deterministic(self) -> None:
        manifest = base_manifest()
        first = gen.render_body(manifest, "root_agents", manifest["root_agents"])
        second = gen.render_body(manifest, "root_agents", manifest["root_agents"])
        self.assertEqual(first, second)

    # --- A3-T14 -----------------------------------------------------------
    def test_a3_t14_traversal_path_refused(self) -> None:
        manifest = base_manifest()
        manifest["subtrees"] = [
            {"path": "../escape/AGENTS.md", "inherits": "root", "sections": [{"key": "x", "body": "y"}]}
        ]
        result = gen.generate(manifest, self.root, apply=True)
        item = entry(result, "../escape/AGENTS.md")
        self.assertEqual(item["action"], "refuse")
        self.assertEqual(item["conflict"], "path-escape")
        self.assertFalse((self.root.parent / "escape" / "AGENTS.md").exists())

    # --- A3-T15 -----------------------------------------------------------
    def test_a3_t15_hand_edits_outside_markers_preserved(self) -> None:
        gen.generate(base_manifest(), self.root, apply=True)
        agents = self.root / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        # Hand-authored trailing note outside the marked region.
        text = text + "\n## Hand-authored appendix\nKeep me.\n"
        # Corrupt the block interior so a refresh is required.
        text = text.replace("Project intent for the wave.", "stale interior text")
        agents.write_text(text, encoding="utf-8")
        result = gen.generate(base_manifest(), self.root, apply=True)
        after = agents.read_text(encoding="utf-8")
        self.assertEqual(entry(result, "AGENTS.md")["action"], "merge")
        self.assertIn("## Hand-authored appendix\nKeep me.", after)
        self.assertIn("Project intent for the wave.", after)
        self.assertNotIn("stale interior text", after)
        self.assertEqual(count_markers(after), (1, 1))

    # --- A3-T16 -----------------------------------------------------------
    def test_a3_t16_duplicate_target_refused(self) -> None:
        manifest = base_manifest()
        manifest["claude_rules"] = [
            {"path": "AGENTS.md", "sections": [{"key": "dup", "body": "collision"}]}
        ]
        result = gen.generate(manifest, self.root, apply=True)
        self.assertFalse(result["ok"])
        self.assertTrue(any(c["reason"] == "duplicate-target" for c in result["conflicts"]), result["conflicts"])

    # --- CLI --------------------------------------------------------------
    def test_cli_plan_writes_nothing_and_reports_json(self) -> None:
        manifest_path = self.root / ".agentic-sdlc" / "instructions.manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(base_manifest()), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "plan", "--manifest", str(manifest_path), "--target", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "plan")
        self.assertFalse((self.root / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
