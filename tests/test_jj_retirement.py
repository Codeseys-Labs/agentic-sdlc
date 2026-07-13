from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
BASH = shutil.which("bash")
SURFACES = (
    ROOT / "mise.toml",
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "commands" / "sdlc-init.md",
    ROOT / "scripts" / "check-agentic-sdlc-prereqs.sh",
    ROOT / "scripts" / "validate-bundle.sh",
    ROOT / "scripts" / "validate_bundle.py",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "SKILL.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "jj-vcs.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "seeds-worktrees.md",
    ROOT / "skills" / "repo-toolchain-gates" / "SKILL.md",
    ROOT / "skills" / "stacked-prs" / "SKILL.md",
    ROOT / "skills" / "stacked-prs-gh-cli" / "SKILL.md",
)
ACTIVE_JJ_PATTERNS = (
    "jj git init",
    "jj git push",
    "jj workspace",
    "jj undo",
    ".jj/",
    "jujutsu",
)


class JjRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.surface_text = {path: path.read_text() for path in SURFACES}

    def test_public_task_graph_has_no_jj_init(self) -> None:
        result = subprocess.run(
            ["mise", "tasks", "--json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tasks = json.loads(result.stdout)
        self.assertNotIn("jj:init", {task["name"] for task in tasks})

    def test_legacy_validator_accepts_retired_task_graph(self) -> None:
        if not BASH:
            self.skipTest("Bash is required for the legacy validator wrapper")
        result = subprocess.run(
            [BASH, str(ROOT / "scripts" / "validate-bundle.sh")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validate-bundle: 0 error(s)", result.stdout)

    def test_jj_is_not_a_mise_tool(self) -> None:
        tools = self.surface_text[ROOT / "mise.toml"].split("[tasks.", 1)[0]
        self.assertNotRegex(tools, r"(?m)^jj\s*=")

    def test_all_public_surfaces_reject_active_jj_guidance(self) -> None:
        for path, text in self.surface_text.items():
            with self.subTest(surface=path):
                if path.name == "jj-vcs.md":
                    self.assertRegex(text, r"(?i)one-release|refus(?:e|al)")
                    self.assertRegex(text, r"(?i)Git worktrees? (?:are|remain) supported")
                    self.assertNotRegex(text, r"(?i)jj\s+(?:git|workspace|bookmark|undo)|\.jj/")
                elif path.name == "SKILL.md" and path.parent.name == "agentic-sdlc-orchestrator":
                    self.assertNotRegex(text, r"(?i)jj\s+(?:git|workspace|bookmark|undo)|\.jj/")
                else:
                    self.assertNotRegex(text, r"(?i)\bjj\b|jujutsu|\.jj/")
                for pattern in ACTIVE_JJ_PATTERNS:
                    self.assertNotIn(pattern, text)

    def test_no_normal_wave_readiness_or_overclaims(self) -> None:
        text = "\n".join(self.surface_text.values())
        self.assertNotRegex(text, r"(?i)jj.{0,80}(?:normal|default|supported)\s+wave")
        self.assertNotRegex(text, r"(?i)(?:work loss|conflict).{0,80}(?:impossible|never|cannot happen)")


if __name__ == "__main__":
    unittest.main()
