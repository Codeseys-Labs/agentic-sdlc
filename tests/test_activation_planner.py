from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import activation_planner as ap
from scripts import instruction_generator as gen


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "activation_planner.py"
MARKER_START = "<!-- agentic-sdlc:start -->"
MARKER_END = "<!-- agentic-sdlc:end -->"
FIXED_NOW = "2026-07-16T00:00:00Z"


def git(target: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def init_repo(target: Path) -> None:
    git(target, "init", "-b", "main")
    git(target, "config", "user.email", "test@example.com")
    git(target, "config", "user.name", "Test")


def instruction_manifest() -> dict:
    return {
        "schema": "agentic-sdlc/instruction-manifest@1",
        "marker": {"start": MARKER_START, "end": MARKER_END},
        "doctrine_pointer": "skills/agentic-sdlc/SKILL.md",
        "root_agents": {
            "path": "AGENTS.md",
            "sections": [
                {"key": "intent", "body": "Ship the wave safely."},
                {"key": "gate", "body": "Run `mise run check` before any commit."},
                {"key": "substrate", "body": "Git-worktree waves only."},
            ],
        },
        "root_claude": {
            "path": "CLAUDE.md",
            "import": "@AGENTS.md",
            "claude_routing": ["/sdlc-init", "/sdlc-frame"],
        },
        "subtrees": [],
        "claude_rules": [],
    }


def passing_gate(target: Path) -> bool:
    """A gate that fails while the reversible fixture is planted and passes once removed."""
    return not any(target.glob(".agentic-sdlc/gate-fixture.*"))


def snapshot(target: Path) -> dict[str, str]:
    """Byte snapshot of the tree, excluding VCS internals and activation metadata."""
    files = {}
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(target).parts
        if parts and parts[0] in (".git", ".agentic-sdlc"):
            continue
        files[str(path.relative_to(target))] = path.read_text(encoding="utf-8")
    return files


class ActivationPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        doctrine = self.root / "skills" / "agentic-sdlc" / "SKILL.md"
        doctrine.parent.mkdir(parents=True)
        doctrine.write_text("---\nname: agentic-sdlc\n---\n# doctrine\n", encoding="utf-8")

    def target(self, name: str) -> Path:
        path = self.root / name
        path.mkdir()
        return path

    # --- A2-T01 -----------------------------------------------------------
    def test_a2_t01_empty_dir_dry_run_plan_no_writes(self) -> None:
        t = self.target("empty")
        plan = ap.plan(t, now=FIXED_NOW)
        self.assertEqual(plan["profile"], "git")
        self.assertEqual(plan["profile_source"], "defaulted")
        item = ap.plan_item(plan, "git-baseline")
        self.assertEqual(item["action"], "create")
        self.assertFalse((t / ".agentic-sdlc").exists())

    # --- A2-T02 -----------------------------------------------------------
    def test_a2_t02_headless_greenfield_apply_commits_readme(self) -> None:
        t = self.target("green")
        result = ap.apply(
            t, yes=True, tty=False, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 2, "blocked": 1},
            gate_runner=passing_gate,
            manifest=instruction_manifest(),
        )
        self.assertEqual(result["exit_code"], 0, result["receipt"])
        receipt = result["receipt"]
        self.assertFalse(receipt["baseline"]["empty_commit"])
        self.assertIn("README.md", receipt["baseline"]["tracked_committed"])
        self.assertTrue(receipt["seeds"]["queue_nonempty"])
        self.assertTrue(receipt["wave_ready"])
        self.assertTrue((t / "README.md").is_file())
        committed = git(t, "ls-files").stdout.split()
        self.assertIn("README.md", committed)

    # --- A2-T03 -----------------------------------------------------------
    def test_a2_t03_existing_clean_dry_run_adopts_baseline(self) -> None:
        t = self.target("existing")
        init_repo(t)
        (t / "app.py").write_text("print('hi')\n", encoding="utf-8")
        (t / "notes.txt").write_text("scratch\n", encoding="utf-8")
        git(t, "add", "app.py")
        git(t, "commit", "-m", "seed")
        plan = ap.plan(t, now=FIXED_NOW)
        item = ap.plan_item(plan, "git-baseline")
        self.assertEqual(item["action"], "adopt")
        self.assertIn("app.py", plan["baseline_inventory"]["tracked"])
        self.assertIn("notes.txt", plan["baseline_inventory"]["untracked_product"])

    # --- A2-T04 -----------------------------------------------------------
    def test_a2_t04_dirty_tree_stops_no_commit(self) -> None:
        t = self.target("dirty")
        init_repo(t)
        (t / "a.py").write_text("x\n", encoding="utf-8")
        git(t, "add", "a.py")
        git(t, "commit", "-m", "seed")
        (t / "a.py").write_text("y\n", encoding="utf-8")  # unstaged change -> dirty
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate,
        )
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("dirty-tree", [s["reason"] for s in result["receipt"]["stops"]])
        head = git(t, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(git(t, "log", "--oneline").stdout.count("\n"), 1)

    # --- A2-T05 -----------------------------------------------------------
    def test_a2_t05_jj_profile_refused_no_writes(self) -> None:
        t = self.target("jj")
        result = ap.apply(t, profile="jj-colocated", yes=True, now=FIXED_NOW)
        self.assertNotEqual(result["exit_code"], 0)
        self.assertEqual(result["receipt"]["status"], "refused")
        self.assertIn("jj-vcs.md", json.dumps(result["receipt"]))
        self.assertFalse((t / ".git").exists())
        self.assertFalse((t / ".agentic-sdlc").exists())

    # --- A2-T06 -----------------------------------------------------------
    def test_a2_t06_agents_foreign_content_merged(self) -> None:
        t = self.target("merge")
        foreign = "# House rules\n\nDo not remove.\n"
        (t / "AGENTS.md").write_text(foreign, encoding="utf-8")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        text = (t / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(foreign.strip(), text)
        self.assertEqual(text.count(MARKER_START), 1)
        self.assertIn("AGENTS.md", result["receipt"]["merged"])

    # --- A2-T07 -----------------------------------------------------------
    def test_a2_t07_agents_correct_block_adopted(self) -> None:
        t = self.target("adopt")
        manifest = instruction_manifest()
        gen.generate(manifest, t, apply=True)  # pre-seed with the exact block
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=manifest,
        )
        self.assertIn("AGENTS.md", result["receipt"]["adopted"])
        self.assertNotIn("AGENTS.md", result["receipt"]["merged"])

    # --- A2-T08 -----------------------------------------------------------
    def test_a2_t08_broken_marker_refused(self) -> None:
        t = self.target("broken")
        (t / "AGENTS.md").write_text(f"{MARKER_START}\nhalf open\n", encoding="utf-8")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        conflicts = result["receipt"]["conflicts"]
        self.assertTrue(any("malformed-marker" == c["reason"] for c in conflicts), conflicts)
        self.assertFalse(result["receipt"]["wave_ready"])

    # --- A2-T09 -----------------------------------------------------------
    def test_a2_t09_claude_hand_authored_stays_thin(self) -> None:
        t = self.target("claude")
        (t / "CLAUDE.md").write_text("@AGENTS.md\n\n# My routing notes\nkeep\n", encoding="utf-8")
        ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        text = (t / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("@AGENTS.md\n"))
        self.assertIn("# My routing notes", text)

    # --- A2-T12 / A2-T13 --------------------------------------------------
    def test_a2_t12_seeds_init_planned_with_guard_when_absent(self) -> None:
        t = self.target("noseeds")
        plan = ap.plan(t, now=FIXED_NOW)
        init_calls = [c for c in plan["seeds_calls"] if "init" in c["call"]]
        self.assertTrue(init_calls)
        self.assertIn("absent", init_calls[0]["guard"])

    def test_a2_t13_seeds_init_skipped_when_present(self) -> None:
        t = self.target("hasseeds")
        (t / ".seeds").mkdir()
        plan = ap.plan(t, now=FIXED_NOW)
        self.assertTrue(plan["baseline_inventory"]["seeds"]["present"])
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": False, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        self.assertFalse(result["receipt"]["seeds"]["init_ran"])

    # --- A2-T14 -----------------------------------------------------------
    def test_a2_t14_empty_queue_blocks_wave_ready(self) -> None:
        t = self.target("emptyq")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 0, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("empty-queue", [s["reason"] for s in result["receipt"]["stops"]])

    # --- A2-T15 -----------------------------------------------------------
    def test_a2_t15_gate_fixture_reversible_no_residue(self) -> None:
        t = self.target("gate")
        observed = []

        def observing_gate(target: Path) -> bool:
            present = any(target.glob(".agentic-sdlc/gate-fixture.*"))
            observed.append(present)
            return not present

        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=observing_gate, manifest=instruction_manifest(),
        )
        self.assertEqual(observed, [True, False])  # fixture present -> fail, removed -> pass
        self.assertTrue(result["receipt"]["gate_proof"]["fixture_fail"])
        self.assertTrue(result["receipt"]["gate_proof"]["clean_pass"])
        self.assertEqual(list(t.glob(".agentic-sdlc/gate-fixture.*")), [])
        # never committed
        if (t / ".git").exists():
            tracked = git(t, "ls-files").stdout
            self.assertNotIn("gate-fixture", tracked)

    # --- A2-T16 -----------------------------------------------------------
    def test_a2_t16_trust_not_auto_approved_headless(self) -> None:
        t = self.target("trust16")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
            trust_requests=[{"kind": "mise", "path": str(t)}],
        )
        actions = result["receipt"]["trust_actions"]
        self.assertTrue(actions)
        self.assertFalse(actions[0]["approved"])
        self.assertEqual(actions[0]["status"], "needs-approval")
        self.assertFalse(result["receipt"]["wave_ready"])  # required trust unverified

    # --- A2-T17 -----------------------------------------------------------
    def test_a2_t17_trust_approved_for_exact_path_only(self) -> None:
        t = self.target("trust17")
        result = ap.apply(
            t, tty=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
            trust_requests=[{"kind": "mise", "path": str(t)}],
            trust_approvals={str(t): True},
            confirm=lambda item: True,
        )
        actions = result["receipt"]["trust_actions"]
        self.assertTrue(actions[0]["approved"])
        self.assertEqual(actions[0]["path"], str(t))

    # --- A2-T18 -----------------------------------------------------------
    def test_a2_t18_cancellation_yields_no_writes(self) -> None:
        t = self.target("cancel")
        result = ap.apply(
            t, tty=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
            confirm=lambda item: False,  # decline
        )
        self.assertNotEqual(result["exit_code"], 0)
        self.assertEqual(result["receipt"]["status"], "cancelled")
        self.assertFalse((t / "AGENTS.md").exists())
        self.assertFalse((t / ".agentic-sdlc").exists())
        self.assertFalse((t / ".git").exists())

    # --- A2-T19 -----------------------------------------------------------
    def test_a2_t19_rerun_is_idempotent(self) -> None:
        t = self.target("idem")
        common = dict(
            yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        first = ap.apply(t, **common)
        self.assertEqual(first["exit_code"], 0, first["receipt"])
        before = snapshot(t)
        second = ap.apply(t, **common)
        after = snapshot(t)
        self.assertEqual(before, after)  # byte-identical tree (excl. .git/.agentic-sdlc)
        self.assertEqual(second["receipt"]["created"], [])
        self.assertEqual(second["receipt"]["merged"], [])

    # --- A2-T20 -----------------------------------------------------------
    def test_a2_t20_ambiguous_ci_stops(self) -> None:
        t = self.target("ci-amb")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
            ci_provider="ambiguous",
        )
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("ci-ambiguous", [s["reason"] for s in result["receipt"]["stops"]])
        self.assertFalse((t / ".github" / "workflows" / "validate.yml").exists())

    # --- A2-T21 -----------------------------------------------------------
    def test_a2_t21_github_ci_invokes_mise_run_check(self) -> None:
        t = self.target("ci-gh")
        ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
            ci_provider="github",
        )
        workflow = t / ".github" / "workflows" / "validate.yml"
        self.assertTrue(workflow.is_file())
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("mise run check", text)

    # --- A2-T22 -----------------------------------------------------------
    def test_a2_t22_deactivate_removes_only_authored(self) -> None:
        t = self.target("deact")
        foreign = "# Keep me\n\nhand-authored\n"
        (t / "AGENTS.md").write_text(foreign, encoding="utf-8")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        receipt = result["receipt"]
        # dry-run deactivate writes nothing
        dry = ap.deactivate(t, receipt=receipt, dry_run=True)
        self.assertEqual(dry["mode"], "plan")
        self.assertIn(foreign.strip(), (t / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn(MARKER_START, (t / "AGENTS.md").read_text(encoding="utf-8"))
        # apply deactivate removes authored block, preserves foreign
        ap.deactivate(t, receipt=receipt, dry_run=False)
        text = (t / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(foreign.strip(), text)
        self.assertNotIn(MARKER_START, text)
        # CLAUDE.md was created by us -> removed entirely
        self.assertFalse((t / "CLAUDE.md").exists())

    # --- A2-T23 -----------------------------------------------------------
    def test_a2_t23_headless_non_derivable_stops(self) -> None:
        t = self.target("ambiguous")
        (t / ".gitignore").write_text("*.log\n", encoding="utf-8")
        (t / "only.log").write_text("ignored\n", encoding="utf-8")
        init_repo(t)  # .gitignore is a product file? it is dot-file; treat as non-product
        # Make .gitignore ignored-only scenario: commit nothing, only ignored + gitignore
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            kind=None,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("needs-input", [s["reason"] for s in result["receipt"]["stops"]])

    # --- A2-T24 -----------------------------------------------------------
    def test_a2_t24_receipt_records_explicit_vs_defaulted(self) -> None:
        t = self.target("sources")
        result = ap.apply(
            t, profile="git", yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        receipt = result["receipt"]
        self.assertEqual(receipt["profile_source"], "explicit")
        # each result records its chosen_source
        for entry in receipt["results"]:
            self.assertIn(entry["chosen_source"], ("explicit", "defaulted", "derived"))

    # --- A3-T18 integration ----------------------------------------------
    def test_a3_t18_plan_item_drives_generator_merge(self) -> None:
        t = self.target("integration")
        (t / "AGENTS.md").write_text("# foreign\n\nbody\n", encoding="utf-8")
        plan = ap.plan(t, now=FIXED_NOW, manifest=instruction_manifest())
        agents_item = next(i for i in plan["items"] if i["target_path"] == "AGENTS.md")
        self.assertEqual(agents_item["action"], "merge")
        result = ap.apply(
            t, yes=True, now=FIXED_NOW,
            seeds={"init_ran": True, "ready": 1, "blocked": 0},
            gate_runner=passing_gate, manifest=instruction_manifest(),
        )
        self.assertIn("AGENTS.md", result["receipt"]["merged"])

    # --- CLI --------------------------------------------------------------
    def test_cli_dry_run_plan_writes_nothing(self) -> None:
        t = self.target("cli")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "plan", "--target", str(t), "--profile", "git"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertFalse((t / ".agentic-sdlc").exists())


if __name__ == "__main__":
    unittest.main()
