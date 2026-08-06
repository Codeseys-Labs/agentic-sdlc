from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "agentic-sdlc" / "tools" / "pass-budget.py"

spec = importlib.util.spec_from_file_location("pass_budget", SCRIPT)
assert spec and spec.loader
pass_budget = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pass_budget
spec.loader.exec_module(pass_budget)


GOAL = "Ship the offline observer"


def run(target: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--goal", GOAL, "--target", str(target)],
        capture_output=True,
        text=True,
    )


class PassBudgetNumbersTests(unittest.TestCase):
    def test_budgets_match_the_ported_source(self) -> None:
        # Ported from pi-lab's PASS_BUDGETS and commands/sdlc-mission.md's stated ceilings.
        self.assertEqual(
            pass_budget.PASS_BUDGETS,
            {"global": 6, "frame": 1, "discover": 2, "research": 2, "plan": 2, "act": 3},
        )


class PassBudgetLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)

    def test_phase_cap_refusal_names_the_blocker(self) -> None:
        slug = pass_budget.slugify(GOAL)
        state = pass_budget.load_state(self.target, slug, GOAL)
        for _ in range(pass_budget.PASS_BUDGETS["frame"]):
            result = pass_budget.charge_pass(self.target, state, "frame")
            self.assertTrue(result["allowed"], result["reason"])
            state = result["state"]
        result = pass_budget.charge_pass(self.target, state, "frame")
        self.assertFalse(result["allowed"])
        self.assertIn("REFUSED", result["reason"])
        self.assertIn("frame", result["reason"])
        self.assertIn("This is a refusal, not a completion", result["reason"])
        self.assertEqual(result["state"]["stop_reason"], "bound-tripped")

    def test_unknown_phase_refused_and_lists_known_phases(self) -> None:
        slug = pass_budget.slugify(GOAL)
        state = pass_budget.load_state(self.target, slug, GOAL)
        result = pass_budget.charge_pass(self.target, state, "bogus")
        self.assertFalse(result["allowed"])
        self.assertIn("unknown phase 'bogus'", result["reason"])
        for phase in ("frame", "discover", "research", "plan", "act"):
            self.assertIn(phase, result["reason"])
        self.assertNotIn("global", result["reason"].split(":", 1)[1].split(";")[0])

    def test_global_cap_refuses_even_when_phase_cap_not_hit(self) -> None:
        slug = pass_budget.slugify(GOAL)
        state = pass_budget.load_state(self.target, slug, GOAL)
        # Spend the global budget (6) across phases with room to spare individually:
        # discover(2) + research(2) + plan(2) = 6, none of which trips its own phase cap.
        sequence = ["discover", "discover", "research", "research", "plan", "plan"]
        for phase in sequence:
            result = pass_budget.charge_pass(self.target, state, phase)
            self.assertTrue(result["allowed"], result["reason"])
            state = result["state"]
        self.assertEqual(state["passes"]["global"], 6)
        # The 7th charge is act(1/3): the phase cap is nowhere near tripped, but global is.
        result = pass_budget.charge_pass(self.target, state, "act")
        self.assertFalse(result["allowed"])
        self.assertIn("REFUSED: global budget", result["reason"])
        self.assertEqual(result["state"]["passes"]["act"], 1)
        self.assertLess(result["state"]["passes"]["act"], pass_budget.PASS_BUDGETS["act"])

    def test_refused_charge_still_persists_the_increment(self) -> None:
        slug = pass_budget.slugify(GOAL)
        state = pass_budget.load_state(self.target, slug, GOAL)
        for _ in range(pass_budget.PASS_BUDGETS["frame"]):
            state = pass_budget.charge_pass(self.target, state, "frame")["state"]
        before_global = state["passes"]["global"]
        result = pass_budget.charge_pass(self.target, state, "frame")
        self.assertFalse(result["allowed"])
        # Count-then-refuse: the refused attempt still incremented and persisted.
        self.assertEqual(result["state"]["passes"]["frame"], pass_budget.PASS_BUDGETS["frame"] + 1)
        self.assertEqual(result["state"]["passes"]["global"], before_global + 1)
        reloaded = pass_budget.load_state(self.target, slug, GOAL)
        self.assertEqual(reloaded["passes"]["frame"], pass_budget.PASS_BUDGETS["frame"] + 1)
        self.assertEqual(reloaded["passes"]["global"], before_global + 1)

    def test_slugify_matches_ported_rules(self) -> None:
        self.assertEqual(pass_budget.slugify("Ship the offline observer!!"), "ship-the-offline-observer")
        self.assertEqual(pass_budget.slugify("   "), "mission")
        self.assertEqual(pass_budget.slugify(""), "mission")
        long_goal = "a" * 80
        self.assertEqual(pass_budget.slugify(long_goal), "a" * 48)


class PassBudgetCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)

    def test_persistence_across_processes(self) -> None:
        first = run(self.target, "charge", "plan")
        self.assertEqual(first.returncode, 0, first.stderr)

        second = run(self.target, "charge", "plan")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("pass 2/2 for plan", second.stdout)

        third = run(self.target, "charge", "plan")
        self.assertEqual(third.returncode, 1, third.stdout)
        self.assertIn("REFUSED", third.stdout)

        status = run(self.target, "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["passes"]["plan"], 3)
        self.assertEqual(payload["passes"]["global"], 3)
        self.assertEqual(payload["stop_reason"], "bound-tripped")

        slug = pass_budget.slugify(GOAL)
        state_path = pass_budget.mission_path(self.target, slug)
        self.assertTrue(state_path.is_file())
        on_disk = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["passes"]["plan"], 3)

    def test_cli_unknown_phase_exit_code(self) -> None:
        completed = run(self.target, "charge", "not-a-phase")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("unknown phase", completed.stdout)

    def test_cli_status_before_any_charge(self) -> None:
        completed = run(self.target, "status")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["passes"], {phase: 0 for phase in pass_budget.PASS_BUDGETS})
        self.assertEqual(payload["stop_reason"], "running")
        self.assertEqual(payload["budgets"], pass_budget.PASS_BUDGETS)


if __name__ == "__main__":
    unittest.main()
