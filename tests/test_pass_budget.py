from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "agentic-sdlc" / "tools" / "pass-budget.py"

spec = importlib.util.spec_from_file_location("pass_budget", SCRIPT)
assert spec and spec.loader
pass_budget = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pass_budget
spec.loader.exec_module(pass_budget)


GOAL = "Ship the offline observer"


def run(target: Path, *args: str, fault: str | None = None) -> subprocess.CompletedProcess:
    """One subprocess with a CONSTRUCTED environment.

    Nothing is inherited from `os.environ`: an ambient fault variable, or an ambient anything
    the tool grows a reading of later, must not be able to redden or green this suite. The
    interpreter is addressed by absolute path, so no PATH entry is needed or consulted.
    """
    env: dict[str, str] = {}
    if fault is not None:
        env[pass_budget.FAULT_ENV] = fault
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args, "--goal", GOAL, "--target", str(target)],
        capture_output=True,
        text=True,
        env=env,
    )


@contextlib.contextmanager
def constructed_environment(**extra: str) -> Iterator[None]:
    """The IN-PROCESS mirror of `run`'s `env={}`: a library call sees a CONSTRUCTED environment.

    `charge_pass` reads the fault seam from `os.environ`, and an in-process call inherits whatever
    the developer exported. With `AGENTIC_SDLC_PASS_BUDGET_FAULT=after-write` in the shell, six of
    this module's library-call tests died on an injected fault they never asked for -- an ambient
    variable deciding a verdict, which is exactly what the subprocess half of this suite refuses to
    permit. `patch.dict(..., clear=True)` builds the environment rather than inheriting it, and
    RESTORES the real one on the way out, so no test leaves shared state mutated for the next.
    """
    with mock.patch.dict(os.environ, dict(extra), clear=True):
        yield


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PassBudgetNumbersTests(unittest.TestCase):
    def test_budgets_match_the_ported_source(self) -> None:
        # Ported from pi-lab's PASS_BUDGETS and commands/sdlc-mission.md's stated ceilings.
        self.assertEqual(
            pass_budget.PASS_BUDGETS,
            {"global": 6, "frame": 1, "discover": 2, "research": 2, "plan": 2, "act": 3},
        )

    def test_exit_codes_are_decision_nine(self) -> None:
        self.assertEqual(
            (
                pass_budget.EXIT_OK,
                pass_budget.EXIT_INTERNAL,
                pass_budget.EXIT_INPUT,
                pass_budget.EXIT_REFUSED,
                pass_budget.EXIT_PARTIAL,
            ),
            (0, 1, 2, 3, 4),
        )


class PassBudgetLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        self.slug = pass_budget.slugify(GOAL)

    def charge(self, state: dict, phase: str, attempt_id: str) -> dict:
        """Every library charge goes through here, so the constructed environment cannot be forgotten."""
        with constructed_environment():
            return pass_budget.charge_pass(self.target, state, phase, attempt_id)

    def fresh(self) -> dict:
        with constructed_environment():
            return pass_budget.load_state(self.target, self.slug, GOAL)

    def test_phase_cap_refusal_names_the_blocker(self) -> None:
        state = self.fresh()
        for index in range(pass_budget.PASS_BUDGETS["frame"]):
            result = self.charge(state, "frame", f"frame-{index}")
            self.assertTrue(result["allowed"], result["reason"])
            state = result["state"]
        result = self.charge(state, "frame", "frame-over")
        self.assertFalse(result["allowed"])
        self.assertIn("REFUSED", result["reason"])
        self.assertIn("frame", result["reason"])
        self.assertIn("This is a refusal, not a completion", result["reason"])
        self.assertEqual(result["state"]["stop_reason"], "bound-tripped")

    def test_unknown_phase_is_an_input_error_before_any_effect(self) -> None:
        state = self.fresh()
        with self.assertRaises(pass_budget.BudgetError) as caught:
            self.charge(state, "bogus", "attempt-1")
        self.assertEqual(caught.exception.code, pass_budget.EXIT_INPUT)
        self.assertIn("unknown phase 'bogus'", caught.exception.reason)
        for phase in ("frame", "discover", "research", "plan", "act"):
            self.assertIn(phase, caught.exception.reason)
        # POSITIVE CONTROL: the same channel accepts the phases it just listed, so the refusal
        # above is about `bogus` and not about the argument being unusable in general.
        self.assertTrue(self.charge(state, "act", "attempt-1")["allowed"])
        # `global` is a budget, never a chargeable phase.
        with self.assertRaises(pass_budget.BudgetError) as caught_global:
            self.charge(self.fresh(), "global", "attempt-2")
        self.assertEqual(caught_global.exception.code, pass_budget.EXIT_INPUT)

    def test_global_cap_refuses_even_when_phase_cap_not_hit(self) -> None:
        state = self.fresh()
        # Spend the global budget (6) across phases with room to spare individually:
        # discover(2) + research(2) + plan(2) = 6, none of which trips its own phase cap.
        sequence = ["discover", "discover", "research", "research", "plan", "plan"]
        for index, phase in enumerate(sequence):
            result = self.charge(state, phase, f"attempt-{index}")
            self.assertTrue(result["allowed"], result["reason"])
            state = result["state"]
        self.assertEqual(state["passes"]["global"], 6)
        # The 7th charge is act(1/3): the phase cap is nowhere near tripped, but global is.
        result = self.charge(state, "act", "attempt-6")
        self.assertFalse(result["allowed"])
        self.assertIn("REFUSED: global budget", result["reason"])
        self.assertEqual(result["state"]["passes"]["act"], 1)
        self.assertLess(result["state"]["passes"]["act"], pass_budget.PASS_BUDGETS["act"])

    def test_refused_charge_still_persists_the_increment(self) -> None:
        state = self.fresh()
        for index in range(pass_budget.PASS_BUDGETS["frame"]):
            state = self.charge(state, "frame", f"frame-{index}")["state"]
        before_global = state["passes"]["global"]
        result = self.charge(state, "frame", "frame-over")
        self.assertFalse(result["allowed"])
        # Count-then-refuse: the refused attempt still incremented and persisted.
        self.assertEqual(result["state"]["passes"]["frame"], pass_budget.PASS_BUDGETS["frame"] + 1)
        self.assertEqual(result["state"]["passes"]["global"], before_global + 1)
        reloaded = self.fresh()
        self.assertEqual(reloaded["passes"]["frame"], pass_budget.PASS_BUDGETS["frame"] + 1)
        self.assertEqual(reloaded["passes"]["global"], before_global + 1)

    def test_slugify_matches_ported_rules(self) -> None:
        self.assertEqual(pass_budget.slugify("Ship the offline observer!!"), "ship-the-offline-observer")
        self.assertEqual(pass_budget.slugify("   "), "mission")
        self.assertEqual(pass_budget.slugify(""), "mission")
        long_goal = "a" * 80
        self.assertEqual(pass_budget.slugify(long_goal), "a" * 48)

    def test_malformed_attempt_id_is_an_input_error(self) -> None:
        state = self.fresh()
        for bad in ("", "-leading-hyphen", "has space", "has/slash", "x" * 65):
            with self.subTest(attempt_id=bad):
                with self.assertRaises(pass_budget.BudgetError) as caught:
                    self.charge(state, "act", bad)
                self.assertEqual(caught.exception.code, pass_budget.EXIT_INPUT)
        # POSITIVE CONTROL: an id of the admitted shape passes the very same check.
        self.assertTrue(self.charge(state, "act", "a" * 64)["allowed"])

    def test_legacy_schema_one_ledger_is_accepted_and_keyed_from_then_on(self) -> None:
        path = pass_budget.mission_path(self.target, self.slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema": "agentic-sdlc/pass-budget-state@1",
                    "goal": GOAL,
                    "slug": self.slug,
                    "passes": {"global": 2, "frame": 1, "discover": 1, "research": 0, "plan": 0, "act": 0},
                    "history": [],
                    "stop_reason": "running",
                }
            ),
            encoding="utf-8",
        )
        state = self.fresh()
        self.assertEqual(state["passes"]["global"], 2)
        first = self.charge(state, "act", "attempt-a")
        self.assertTrue(first["allowed"])
        self.assertEqual(first["state"]["schema"], pass_budget.SCHEMA)
        digest = sha256_of(path)
        replay = self.charge(self.fresh(), "act", "attempt-a")
        self.assertEqual(replay["reason"], first["reason"])
        self.assertEqual(sha256_of(path), digest)

    def test_unreadable_schema_is_a_clean_refusal(self) -> None:
        path = pass_budget.mission_path(self.target, self.slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema": "somebody-elses/ledger@9", "passes": {}}), encoding="utf-8")
        with self.assertRaises(pass_budget.BudgetError) as caught:
            self.fresh()
        self.assertEqual(caught.exception.code, pass_budget.EXIT_REFUSED)
        # POSITIVE CONTROL: the same reader accepts this tool's own schema at the same path.
        path.write_text(
            json.dumps(
                {
                    "schema": pass_budget.SCHEMA,
                    "goal": GOAL,
                    "slug": self.slug,
                    "passes": {phase: 0 for phase in pass_budget.PASS_BUDGETS},
                    "charges": {},
                    "history": [],
                    "stop_reason": "running",
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.fresh()["schema"], pass_budget.SCHEMA)


class PassBudgetIdempotencyTests(unittest.TestCase):
    """agentic-sdlc-f891: a retried charge for the SAME logical attempt must converge."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        self.slug = pass_budget.slugify(GOAL)
        self.path = pass_budget.mission_path(self.target, self.slug)

    def test_regression_retrying_one_attempt_does_not_spend_a_second_pass(self) -> None:
        """The reproduced defect: charge, retry the same attempt, ledger double-charged."""
        first = run(self.target, "charge", "act", "--attempt-id", "attempt-a")
        self.assertEqual(first.returncode, 0, first.stderr)
        after_first = json.loads(self.path.read_text(encoding="utf-8"))["passes"]
        self.assertEqual((after_first["act"], after_first["global"]), (1, 1))

        retry = run(self.target, "charge", "act", "--attempt-id", "attempt-a")
        self.assertEqual(retry.returncode, 0, retry.stderr)
        after_retry = json.loads(self.path.read_text(encoding="utf-8"))["passes"]
        # Before the fix this was (2, 2): one logical attempt spent two passes against both
        # the phase budget and the global budget.
        self.assertEqual((after_retry["act"], after_retry["global"]), (1, 1))

    def test_keyed_retry_returns_the_same_result_and_leaves_the_ledger_byte_identical(self) -> None:
        first = run(self.target, "charge", "plan", "--attempt-id", "attempt-a")
        self.assertEqual(first.returncode, 0, first.stderr)
        digest = sha256_of(self.path)

        retry = run(self.target, "charge", "plan", "--attempt-id", "attempt-a")
        self.assertEqual(retry.returncode, first.returncode)
        self.assertEqual(retry.stdout, first.stdout)
        self.assertEqual(sha256_of(self.path), digest)

        # POSITIVE CONTROL: the digest channel does move when a real second charge lands, so
        # the unchanged digest above is convergence and not a frozen assertion.
        other = run(self.target, "charge", "plan", "--attempt-id", "attempt-b")
        self.assertEqual(other.returncode, 0, other.stderr)
        self.assertNotEqual(sha256_of(self.path), digest)

    def test_two_different_keys_both_charge(self) -> None:
        for index, attempt in enumerate(("attempt-a", "attempt-b"), start=1):
            completed = run(self.target, "charge", "act", "--attempt-id", attempt)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(f"pass {index}/3 for act", completed.stdout)
        passes = json.loads(self.path.read_text(encoding="utf-8"))["passes"]
        self.assertEqual((passes["act"], passes["global"]), (2, 2))

    def test_a_refused_charge_converges_to_the_same_refusal(self) -> None:
        for attempt in ("f-1",):
            self.assertEqual(run(self.target, "charge", "frame", "--attempt-id", attempt).returncode, 0)
        refused = run(self.target, "charge", "frame", "--attempt-id", "f-2")
        self.assertEqual(refused.returncode, 0, refused.stderr)
        self.assertIn("REFUSED", refused.stdout)
        digest = sha256_of(self.path)
        replay = run(self.target, "charge", "frame", "--attempt-id", "f-2")
        self.assertEqual(replay.stdout, refused.stdout)
        self.assertEqual(replay.returncode, refused.returncode)
        self.assertEqual(sha256_of(self.path), digest)

    def test_reusing_one_key_for_a_different_phase_is_refused_before_any_effect(self) -> None:
        self.assertEqual(run(self.target, "charge", "act", "--attempt-id", "attempt-a").returncode, 0)
        digest = sha256_of(self.path)
        conflict = run(self.target, "charge", "plan", "--attempt-id", "attempt-a")
        self.assertEqual(conflict.returncode, pass_budget.EXIT_REFUSED, conflict.stderr)
        self.assertIn("attempt-a", conflict.stderr)
        self.assertEqual(sha256_of(self.path), digest)
        # POSITIVE CONTROL: `plan` itself is chargeable under a key of its own, so the refusal
        # is about the reused key and not about the phase.
        self.assertEqual(run(self.target, "charge", "plan", "--attempt-id", "attempt-b").returncode, 0)
        self.assertNotEqual(sha256_of(self.path), digest)

    def test_an_unkeyed_charge_is_refused_as_a_grammar_error(self) -> None:
        unkeyed = run(self.target, "charge", "act")
        self.assertEqual(unkeyed.returncode, pass_budget.EXIT_INPUT, unkeyed.stderr)
        self.assertIn("attempt-id", unkeyed.stderr)
        self.assertFalse(self.path.exists())
        # POSITIVE CONTROL: the keyed form at this same target does create the ledger, so the
        # absence above is the refusal and not an unwritable target directory.
        self.assertEqual(run(self.target, "charge", "act", "--attempt-id", "attempt-a").returncode, 0)
        self.assertTrue(self.path.is_file())


class PassBudgetEffectTests(unittest.TestCase):
    """Decision 9 honesty: what already happened decides the code, at one derivation point."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        self.slug = pass_budget.slugify(GOAL)
        self.path = pass_budget.mission_path(self.target, self.slug)

    def test_crash_after_the_durable_write_still_costs_the_pass(self) -> None:
        """The property the fix must NOT break, asserted as a positive control on both sides."""
        crashed = run(self.target, "charge", "act", "--attempt-id", "attempt-a", fault="after-write")
        self.assertEqual(crashed.returncode, pass_budget.EXIT_PARTIAL, crashed.stderr)
        self.assertTrue(self.path.is_file(), "the durable increment must survive the crash")
        passes = json.loads(self.path.read_text(encoding="utf-8"))["passes"]
        self.assertEqual((passes["act"], passes["global"]), (1, 1), "a crash must not hand out a free pass")

        # POSITIVE CONTROL for the other direction: crashing BEFORE the write leaves no ledger,
        # which proves the ledger above was written by the charge and not by the fault seam.
        other = Path(self.tmp.name) / "before"
        early = run(other, "charge", "act", "--attempt-id", "attempt-a", fault="before-write")
        self.assertEqual(early.returncode, pass_budget.EXIT_INTERNAL, early.stderr)
        self.assertFalse(pass_budget.mission_path(other, self.slug).exists())

    def test_crash_after_the_durable_write_reports_four_on_an_existing_ledger_too(self) -> None:
        """The ordinary case: `.sdlc/` already exists, so nothing but the write can be admitted.

        Written when creating `.sdlc/` was still an admitted effect and a mutation that deleted the
        temp-file admission survived the test above by riding on it. That admission is gone (see
        `_ensure_ledger_directory`), so both tests now turn on the write's own admission -- and this
        one keeps the input where it is unmistakably the only candidate.
        """
        first = run(self.target, "charge", "act", "--attempt-id", "attempt-a")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(self.path.parent.is_dir())

        crashed = run(self.target, "charge", "act", "--attempt-id", "attempt-b", fault="after-write")
        self.assertEqual(crashed.returncode, pass_budget.EXIT_PARTIAL, crashed.stderr)
        self.assertIn("already happened", crashed.stderr)
        passes = json.loads(self.path.read_text(encoding="utf-8"))["passes"]
        self.assertEqual((passes["act"], passes["global"]), (2, 2))

        # POSITIVE CONTROL: the same second charge without the fault also lands 2/2 at exit 0, so
        # the count above is the charge's own increment and not something the seam wrote.
        clean = Path(self.tmp.name) / "clean"
        self.assertEqual(run(clean, "charge", "act", "--attempt-id", "attempt-a").returncode, 0)
        self.assertEqual(run(clean, "charge", "act", "--attempt-id", "attempt-b").returncode, 0)
        clean_passes = json.loads(pass_budget.mission_path(clean, self.slug).read_text(encoding="utf-8"))["passes"]
        self.assertEqual((clean_passes["act"], clean_passes["global"]), (2, 2))

    def test_a_landed_increment_never_reports_a_clean_pre_effect_refusal(self) -> None:
        crashed = run(self.target, "charge", "act", "--attempt-id", "attempt-a", fault="after-write:3")
        # The site asked for 3 (a clean refusal); the ledger has moved, so the honest answer is 4.
        self.assertEqual(crashed.returncode, pass_budget.EXIT_PARTIAL, crashed.stderr)
        self.assertNotEqual(crashed.returncode, pass_budget.EXIT_REFUSED)
        self.assertIn("already happened", crashed.stderr)
        # POSITIVE CONTROL: the same requested 3 BEFORE any effect comes out as 3, so the
        # escalation channel really can carry 3 and the 4 above is derived, not hardcoded.
        other = Path(self.tmp.name) / "before"
        early = run(other, "charge", "act", "--attempt-id", "attempt-a", fault="before-write:3")
        self.assertEqual(early.returncode, pass_budget.EXIT_REFUSED, early.stderr)
        self.assertNotIn("already happened", early.stderr)

    def test_a_budget_refusal_is_a_completed_charge_not_a_failure(self) -> None:
        self.assertEqual(run(self.target, "charge", "frame", "--attempt-id", "f-1").returncode, 0)
        refused = run(self.target, "charge", "frame", "--attempt-id", "f-2")
        # Decision 9 has no code for "refused AFTER the effect the doctrine requires": the
        # charge completed exactly, so the verdict rides in the result, not in the exit code.
        self.assertEqual(refused.returncode, pass_budget.EXIT_OK, refused.stderr)
        self.assertIn("REFUSED", refused.stdout)
        self.assertIn("REFUSED", refused.stderr)  # loud on the advisory channel too
        passes = json.loads(self.path.read_text(encoding="utf-8"))["passes"]
        self.assertEqual(passes["frame"], 2)
        # POSITIVE CONTROL: exit 0 here is not "every charge exits 0" -- a grammar error on the
        # same verb still moves the code.
        self.assertEqual(run(self.target, "charge", "nope", "--attempt-id", "f-3").returncode, pass_budget.EXIT_INPUT)

    def test_a_corrupt_ledger_is_a_clean_refusal_for_charge_and_status(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not json", encoding="utf-8")
        digest = sha256_of(self.path)
        charge = run(self.target, "charge", "act", "--attempt-id", "attempt-a")
        self.assertEqual(charge.returncode, pass_budget.EXIT_REFUSED, charge.stderr)
        status = run(self.target, "status")
        self.assertEqual(status.returncode, pass_budget.EXIT_REFUSED, status.stderr)
        self.assertEqual(sha256_of(self.path), digest, "a refused read must not rewrite the ledger")

    def test_a_ledger_whose_bytes_are_not_utf8_is_a_clean_refusal_for_charge_and_status(self) -> None:
        """agentic-sdlc-94d8: the ledger is DECODED on the read, and a decode error is no OSError.

        `read_text` raises `UnicodeDecodeError` -- a `ValueError` -- so the read handler's `OSError`
        never saw it and it escaped to the top-level catch-all as `internal: unexpected
        UnicodeDecodeError` at exit 1, while this module's own docstring promises that a ledger it
        cannot read is a clean refusal at exit 3.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b'\xff\xfe{"schema": "agentic-sdlc/pass-budget-state@2"}\n')
        digest = sha256_of(self.path)
        charge = run(self.target, "charge", "act", "--attempt-id", "attempt-a")
        self.assertEqual(charge.returncode, pass_budget.EXIT_REFUSED, charge.stderr)
        self.assertIn("cannot read the ledger", charge.stderr)
        self.assertNotIn("unexpected UnicodeDecodeError", charge.stderr)
        status = run(self.target, "status")
        self.assertEqual(status.returncode, pass_budget.EXIT_REFUSED, status.stderr)
        self.assertIn("cannot read the ledger", status.stderr)
        self.assertEqual(sha256_of(self.path), digest, "a refused read must not rewrite the ledger")
        # POSITIVE CONTROL: both verbs at this same path still work once the bytes are UTF-8, so the
        # two refusals above are about the undecodable ledger and not about the target or the verbs.
        self.path.unlink()
        charged = run(self.target, "charge", "act", "--attempt-id", "attempt-a")
        self.assertEqual(charged.returncode, pass_budget.EXIT_OK, charged.stderr)
        self.assertIn("pass 1/3 for act", charged.stdout)
        self.assertEqual(run(self.target, "status").returncode, pass_budget.EXIT_OK)


class PassBudgetCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)

    def test_persistence_across_processes(self) -> None:
        first = run(self.target, "charge", "plan", "--attempt-id", "p-1")
        self.assertEqual(first.returncode, 0, first.stderr)

        second = run(self.target, "charge", "plan", "--attempt-id", "p-2")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("pass 2/2 for plan", second.stdout)

        third = run(self.target, "charge", "plan", "--attempt-id", "p-3")
        self.assertEqual(third.returncode, 0, third.stdout)
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
        self.assertEqual(sorted(on_disk["charges"]), ["p-1", "p-2", "p-3"])

    def test_cli_unknown_phase_exit_code(self) -> None:
        completed = run(self.target, "charge", "not-a-phase", "--attempt-id", "attempt-a")
        self.assertEqual(completed.returncode, pass_budget.EXIT_INPUT)
        self.assertIn("unknown phase", completed.stderr)

    def test_cli_status_before_any_charge(self) -> None:
        completed = run(self.target, "status")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["passes"], {phase: 0 for phase in pass_budget.PASS_BUDGETS})
        self.assertEqual(payload["stop_reason"], "running")
        self.assertEqual(payload["budgets"], pass_budget.PASS_BUDGETS)
        self.assertEqual(payload["charges"], 0)

    def test_an_unknown_fault_point_is_an_input_error(self) -> None:
        completed = run(self.target, "charge", "act", "--attempt-id", "attempt-a", fault="not-a-point")
        self.assertEqual(completed.returncode, pass_budget.EXIT_INPUT, completed.stderr)


class AmbientEnvironmentTests(unittest.TestCase):
    """agentic-sdlc-91d7: an ambient variable must not be able to redden or green this suite."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        self.slug = pass_budget.slugify(GOAL)

    def library_charge(self, attempt_id: str, **environment: str) -> dict:
        with constructed_environment(**environment):
            state = pass_budget.load_state(self.target, self.slug, GOAL)
            return pass_budget.charge_pass(self.target, state, "act", attempt_id)

    def test_an_exported_fault_variable_cannot_reach_a_library_charge(self) -> None:
        # Whatever the developer's shell exported is the state this test must survive AND restore,
        # so it is read rather than assumed: this suite is run both ways deliberately.
        ambient = os.environ.get(pass_budget.FAULT_ENV)
        with mock.patch.dict(os.environ, {pass_budget.FAULT_ENV: "after-write"}, clear=False):
            self.assertTrue(self.library_charge("attempt-a")["allowed"])
            # POSITIVE CONTROL: the seam still fires when a test ASKS for it through the constructed
            # environment, so the charge above is the construction working and not a dead seam.
            with self.assertRaises(pass_budget.BudgetError) as caught:
                self.library_charge("attempt-b", **{pass_budget.FAULT_ENV: "after-write"})
            self.assertEqual(caught.exception.code, pass_budget.EXIT_INTERNAL)
            # ... and the value in scope is RESTORED rather than mutated for whatever runs next.
            self.assertEqual(os.environ[pass_budget.FAULT_ENV], "after-write")
        self.assertEqual(os.environ.get(pass_budget.FAULT_ENV), ambient)


class PassBudgetConcurrencyTests(unittest.TestCase):
    """agentic-sdlc-6bef: concurrent charges must be recorded or refused, never told-ok-and-dropped.

    The race here is UNALIGNED on purpose. The rendezvous harness this class used to carry blocked
    its second child on a file the first wrote only AFTER `main` returned, so the two charges never
    overlapped in the window that actually loses writes -- it certified a property it did not test.
    Plain back-to-back spawns do overlap there: measured against the compare-and-swap alone, four
    charges on one fresh ledger all exited 0, all printed `pass 1/3`, and left ONE recorded, in ten
    trials out of ten. The re-read costs about 0.1 ms; the write it does not cover costs 3-7 ms.
    """

    CONCURRENT_CHARGES = 4
    TRIALS = 5

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.slug = pass_budget.slugify(GOAL)
        self.path = pass_budget.mission_path(self.target, self.slug)
        self.lock = pass_budget.mission_lock_path(self.target, self.slug)

    def spawn(self, target: Path, attempt_id: str) -> subprocess.Popen[str]:
        """One real CLI charge, started and NOT waited for, with a constructed empty environment."""
        return subprocess.Popen(
            [
                sys.executable, "-B", str(SCRIPT), "charge", "act",
                "--goal", GOAL, "--target", str(target), "--attempt-id", attempt_id,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={},
        )

    def ledger(self, path: Path | None = None) -> dict:
        return json.loads((path or self.path).read_text(encoding="utf-8"))

    def charge_in_process(self, attempt_id: str) -> tuple[int, str]:
        """Drive `main` here, so the DERIVED exit code and the stderr text are both observable."""
        stderr, stdout = io.StringIO(), io.StringIO()
        with constructed_environment(), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
            code = pass_budget.main(
                ["charge", "act", "--goal", GOAL, "--target", str(self.target), "--attempt-id", attempt_id]
            )
        return code, stderr.getvalue()

    def test_unaligned_concurrent_charges_are_each_recorded_or_refused(self) -> None:
        """THE INVARIANT: exit-0 count == recorded charges == pass counts, over an unforced race."""
        for trial in range(self.TRIALS):
            with self.subTest(trial=trial):
                room = tempfile.TemporaryDirectory()
                self.addCleanup(room.cleanup)
                target = Path(room.name) / "target"  # a FRESH ledger per trial: the measured case
                path = pass_budget.mission_path(target, self.slug)
                attempts = sorted(f"attempt-{index}" for index in range(self.CONCURRENT_CHARGES))
                children = {attempt: self.spawn(target, attempt) for attempt in attempts}
                outcomes: dict[str, tuple[int, str, str]] = {}
                for attempt, child in children.items():
                    out, err = child.communicate(timeout=120)
                    outcomes[attempt] = (child.returncode, out, err)

                told_ok = sorted(a for a, (code, _, _) in outcomes.items() if code == pass_budget.EXIT_OK)
                refused = sorted(a for a, (code, _, _) in outcomes.items() if code == pass_budget.EXIT_REFUSED)
                self.assertEqual(sorted(told_ok + refused), attempts, f"every charge is 0 or 3: {outcomes}")
                self.assertTrue(told_ok, f"a race in which nothing lands is a livelock, not safety: {outcomes}")

                ledger = self.ledger(path)
                self.assertEqual(sorted(ledger["charges"]), told_ok, f"told ok but not recorded: {outcomes}")
                self.assertEqual(ledger["passes"]["act"], len(told_ok), outcomes)
                self.assertEqual(ledger["passes"]["global"], len(told_ok), outcomes)

                for attempt in refused:
                    _, out, err = outcomes[attempt]
                    # The dropped charges printed `pass 1/3` and said nothing on stderr. A refused
                    # charge claims no pass at all, and names contention or the stale load it saw.
                    self.assertEqual(out, "", f"{attempt} was refused and must claim no pass: {out!r}")
                    self.assertTrue(
                        "changed after this charge loaded it" in err or "holds the mission lock" in err,
                        f"{attempt} refused without naming why: {err!r}",
                    )
                    self.assertNotIn("already happened", err)

    def test_a_held_lock_refuses_the_second_charge_by_name_within_the_deadline(self) -> None:
        """DETERMINISTIC contention: the wait is bounded, and expiry is a clean refusal naming it.

        The lock directory is created by hand, which is exactly the residue a holder killed with
        `SIGKILL` leaves behind -- there is no automatic reclaim, so this is the recovery story too.
        """
        self.assertEqual(run(self.target, "charge", "act", "--attempt-id", "a-1").returncode, pass_budget.EXIT_OK)
        digest = sha256_of(self.path)
        self.lock.mkdir()

        started = time.monotonic()
        with mock.patch.object(pass_budget, "LOCK_DEADLINE_SECONDS", 0.05):
            code, err = self.charge_in_process("a-2")
        waited = time.monotonic() - started

        self.assertEqual(code, pass_budget.EXIT_REFUSED, err)
        self.assertIn("holds the mission lock", err)
        self.assertIn("contention", err)
        self.assertIn(str(self.lock), err, "the refusal must name the directory an operator removes")
        self.assertNotIn("already happened", err)
        self.assertLess(waited, 3.0, "the wait is bounded by the deadline, not by the holder")
        self.assertEqual(sha256_of(self.path), digest, "a charge that never took the lock wrote nothing")

        # POSITIVE CONTROL: release the lock and the very same charge lands, so the refusal above is
        # about the held lock and not about the attempt, the phase, or an exhausted budget.
        self.lock.rmdir()
        with mock.patch.object(pass_budget, "LOCK_DEADLINE_SECONDS", 0.05):
            code, err = self.charge_in_process("a-2")
        self.assertEqual(code, pass_budget.EXIT_OK, err)
        self.assertEqual(sorted(self.ledger()["charges"]), ["a-1", "a-2"])

    def test_a_stale_load_is_refused_cleanly_even_when_the_charge_created_the_directory(self) -> None:
        """The compare-and-swap, kept as the second line -- and the effect floor it must not trip.

        The stale state is manufactured rather than raced for: the ledger it was loaded from is
        removed underneath it together with `.sdlc/`, so this charge has to re-create that directory
        before the re-read can refuse. An empty container directory is not a partial ledger, so the
        derived code stays 3 with nothing admitted -- admitting it made a losing racer print
        `nothing was written` and `this is a PARTIAL result` in one breath, at exit 4.
        """
        self.assertEqual(run(self.target, "charge", "act", "--attempt-id", "a-1").returncode, pass_budget.EXIT_OK)
        with constructed_environment():
            stale = pass_budget.load_state(self.target, self.slug, GOAL)
        self.path.unlink()
        self.path.parent.rmdir()

        with constructed_environment(), pass_budget._effect_ledger() as effects:
            with self.assertRaises(pass_budget.BudgetError) as caught:
                pass_budget.charge_pass(self.target, stale, "act", "a-2")
            self.assertEqual(caught.exception.code, pass_budget.EXIT_REFUSED)
            self.assertIn("changed after this charge loaded it", caught.exception.reason)
            self.assertEqual(effects.admitted, [], "an empty ledger directory is not an admitted effect")
            self.assertEqual(pass_budget._report_failure(caught.exception)[2], pass_budget.EXIT_REFUSED)
        self.assertTrue(self.path.parent.is_dir(), "the charge did re-create the directory it refused in")
        self.assertFalse(self.path.exists(), "and it wrote no ledger there")
        self.assertFalse(self.lock.exists(), "and it released the lock it refused under")

        # A REFUSAL IS NOT A LOST PASS, and the POSITIVE CONTROL for the mechanism: the same attempt
        # id, retried over a fresh load, charges exactly once.
        retry = run(self.target, "charge", "act", "--attempt-id", "a-2")
        self.assertEqual(retry.returncode, pass_budget.EXIT_OK, retry.stderr)
        self.assertEqual(sorted(self.ledger()["charges"]), ["a-2"])

    def test_the_lock_directory_never_outlives_the_charge_that_took_it(self) -> None:
        """Release is in a `finally`, so not even a fault raised inside the lock can orphan it."""
        self.assertEqual(run(self.target, "charge", "act", "--attempt-id", "a-1").returncode, pass_budget.EXIT_OK)
        self.assertFalse(self.lock.exists(), "a completed charge released the lock")

        crashed = run(self.target, "charge", "act", "--attempt-id", "a-2", fault="after-write")
        self.assertEqual(crashed.returncode, pass_budget.EXIT_PARTIAL, crashed.stderr)
        self.assertFalse(self.lock.exists(), "a charge that died after its write still released the lock")

        # POSITIVE CONTROL: the next charge is not blocked by residue, and it charges on top of what
        # the crashed charge had already written.
        third = run(self.target, "charge", "act", "--attempt-id", "a-3")
        self.assertEqual(third.returncode, pass_budget.EXIT_OK, third.stderr)
        self.assertIn("pass 3/3 for act", third.stdout)

    def test_two_sequential_charges_are_not_mistaken_for_a_stale_load(self) -> None:
        """POSITIVE CONTROL for the whole mechanism: ordinary back-to-back charges still both land.

        A lock that never released, or a compare-and-swap that refused everything, would pass every
        assertion in the tests above.
        """
        for index, attempt in enumerate(("attempt-a", "attempt-b"), start=1):
            completed = run(self.target, "charge", "act", "--attempt-id", attempt)
            self.assertEqual(completed.returncode, pass_budget.EXIT_OK, completed.stderr)
            self.assertIn(f"pass {index}/3 for act", completed.stdout)
        self.assertEqual(sorted(self.ledger()["charges"]), ["attempt-a", "attempt-b"])


if __name__ == "__main__":
    unittest.main()
