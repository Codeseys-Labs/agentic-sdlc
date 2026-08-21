from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import activation_planner as ap


SCRIPT = ROOT / "scripts" / "activation_planner.py"


def git(target: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(target), *args], check=check, capture_output=True, text=True)


def init_repo(target: Path) -> None:
    git(target, "init", "-b", "main")
    git(target, "config", "user.name", "test")
    git(target, "config", "user.email", "test@example.invalid")
    (target / "seed.txt").write_text("seed\n")
    git(target, "add", "seed.txt")
    git(target, "commit", "-m", "seed")


def manifest() -> dict:
    return {
        "schema": "agentic-sdlc/instruction-manifest@2",
        "marker": {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"},
        "doctrine_pointer": "literal pointer",
        "outputs": [{"path": "AGENTS.md", "kind": "root_agents", "prefix": "", "sections": [{"key": "intent", "body": "safe"}]}],
    }


class PlannerCompatibilityTests(unittest.TestCase):
    def test_source_imports_expose_canonical_api(self) -> None:
        self.assertEqual(ap.PLAN_SCHEMA, "agentic-sdlc/activation-plan@2")
        self.assertTrue(callable(ap.plan_command))

    def test_cli_usage_refuses_old_surface(self) -> None:
        completed = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0)
        self.assertIn("recover", completed.stdout)
        self.assertNotIn("deactivate", completed.stdout)


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))

    def test_plan_is_read_only_and_binds_one_entry(self) -> None:
        before = sorted(path.relative_to(self.target) for path in self.target.rglob("*") if ".git" not in path.parts)
        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(len(result["plan"]["entries"]), 1)
        after = sorted(path.relative_to(self.target) for path in self.target.rglob("*") if ".git" not in path.parts)
        self.assertEqual(before, after)

    def test_non_git_and_dirty_tree_refused(self) -> None:
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        result, code = ap.plan_command(plain, self.manifest, "AGENTS.md")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "unsupported")
        (self.target / "seed.txt").write_text("dirty\n")
        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "refused")

    def test_a_plan_result_stamps_the_head_it_observed_and_a_refusal_stamps_none(self) -> None:
        # agentic-sdlc-5ee7: the result carries the freshness anchor `activation-result.py` binds the
        # terminal-state chain to. The key is always present, so "no head observed" (a refusal) is
        # distinguishable from "written before heads were stamped" (no key at all).
        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 0, result)
        observed = result["plan"]["git"]
        self.assertEqual(result["head"], {"commit": observed["head"], "tree": observed["tree"]})
        # The tree is derived from the observed commit, so it is that commit's own tree.
        rendered = subprocess.run(
            ["git", "rev-parse", f"{observed['head']}^{{tree}}"],
            cwd=str(self.target), capture_output=True, text=True, check=True,
        )
        self.assertEqual(observed["tree"], rendered.stdout.strip())
        # A refusal observed no head, and says so with a null rather than by omitting the key.
        (self.target / "seed.txt").write_text("dirty\n")
        refused, refused_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(refused_code, 1)
        self.assertIn("head", refused)
        self.assertIsNone(refused["head"])

    def test_cli_plan_prints_exactly_one_canonical_object(self) -> None:
        completed = subprocess.run([sys.executable, str(SCRIPT), "plan", "--target", str(self.target), "--manifest", str(self.manifest), "--entry", "AGENTS.md"], capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout, ap.canonical_bytes(json.loads(completed.stdout)))


if __name__ == "__main__":
    unittest.main()
