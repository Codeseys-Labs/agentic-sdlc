from __future__ import annotations

import ast
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
# The canonical module `SCRIPT` loads. The exit-class census reads these bytes, not the loader's.
PLANNER = ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-planner.py"


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
        # agentic-sdlc-3d9a: both of these are completed read-only checks that named a
        # refusal and touched nothing, so both are Decision 9's 3. They used to be 1 --
        # the code reserved for an unexpected internal failure -- because `ActivationError`
        # defaulted its class and neither raise site said otherwise.
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        result, code = ap.plan_command(plain, self.manifest, "AGENTS.md")
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["exit_code"], 3)
        (self.target / "seed.txt").write_text("dirty\n")
        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["effect"], ap.EFFECT_NONE)

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
        self.assertEqual(refused_code, 3)
        self.assertIn("head", refused)
        self.assertIsNone(refused["head"])

    def test_cli_plan_prints_exactly_one_canonical_object(self) -> None:
        completed = subprocess.run([sys.executable, str(SCRIPT), "plan", "--target", str(self.target), "--manifest", str(self.manifest), "--entry", "AGENTS.md"], capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout, ap.canonical_bytes(json.loads(completed.stdout)))


class ExitClassConformanceTests(unittest.TestCase):
    """agentic-sdlc-3d9a: every refusal states its Implementation Decision 9 class.

    `ActivationError` used to default `code=1`, so 85 named refusals plus one explicit site
    reported themselves at the code reserved for an UNEXPECTED INTERNAL FAILURE while their own
    result document said `status: refused, effect: none`. These tests are written against the
    property, not against a list of numbers: one assertion (`assertClassIsHonest`) is applied
    both to refusals that must never be 1 and to an honest `effect_unknown` record that must
    still be allowed to be 4, so "no record exits 1" cannot be satisfied by banning a number.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))

    def assertClassIsHonest(self, result: dict, code: int, label: str) -> None:
        """THE assertion both directions of the mutation test are made against.

        It is deliberately a relationship between the document and the exit, not a set of
        permitted numbers: an `effect: none` verdict may not exit 1 (it named its refusal, so
        the interpreter's unnamed-failure code is a lie) and it may not exit 4 (nothing
        happened, so there is nothing partial to report); an exit 4 must carry the unknown
        effect that justifies it.
        """
        self.assertEqual(code, result["exit_code"], f"{label}: exit disagrees with the document")
        self.assertIn(code, {0, 2, 3, 4}, f"{label}: 1 is reserved for a failure this module never named -- {result}")
        if result["effect"] == ap.EFFECT_NONE:
            self.assertNotEqual(code, 1, f"{label}: reported no effect at the internal-failure code -- {result}")
            self.assertNotEqual(code, 4, f"{label}: reported no effect at the admitted-effect code -- {result}")
            self.assertEqual(result["admitted_effects"], [], f"{label}: claimed no effect over a non-empty ledger -- {result}")
        if code == 4:
            self.assertEqual(result["effect"], ap.EFFECT_UNKNOWN, f"{label}: exit 4 without an unknown effect -- {result}")

    def test_no_effect_none_refusal_reports_an_unexpected_internal_failure(self) -> None:
        missing = Path(self.tmp.name) / "not-a-repo"
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        dirty = Path(self.tmp.name) / "dirty"
        dirty.mkdir()
        init_repo(dirty)
        (dirty / "seed.txt").write_text("dirty\n")
        bad_plan = Path(self.tmp.name) / "plan.json"
        bad_plan.write_bytes(b'{"schema":"agentic-sdlc/activation-plan@2"}')
        cases = {
            "plan, manifest that cannot be opened": ap.plan_command(self.target, Path(self.tmp.name) / "absent.json", "AGENTS.md"),
            "plan, target that is not a repository": ap.plan_command(plain, self.manifest, "AGENTS.md"),
            "plan, dirty worktree": ap.plan_command(dirty, self.manifest, "AGENTS.md"),
            "plan, entry outside the target": ap.plan_command(self.target, self.manifest, "../escape.md"),
            "status, supplied target that does not exist": ap.status_command(missing),
            "status, idle repository": ap.status_command(self.target),
            "status, relative target path": ap.status_command(Path("relative-not-absolute")),
            "recover inspect, supplied target that does not exist": ap.recover_inspect_command(missing),
            "recover inspect, idle repository": ap.recover_inspect_command(self.target),
            "apply, plan document that fails its own schema": ap.apply_command(bad_plan, self.manifest, bad_plan),
        }
        observed = {}
        for label, (result, code) in cases.items():
            with self.subTest(case=label):
                self.assertClassIsHonest(result, code, label)
                observed[label] = code
        # The classes are distinct verdicts, not one substituted number: an unusable supplied
        # input is 2, a completed check that declines is 3, and a valid query is 0. Without this
        # the whole table could collapse onto a single non-1 code and still pass.
        self.assertEqual(observed["plan, manifest that cannot be opened"], 2)
        self.assertEqual(observed["status, supplied target that does not exist"], 2)
        self.assertEqual(observed["status, relative target path"], 2)
        self.assertEqual(observed["plan, target that is not a repository"], 3)
        self.assertEqual(observed["plan, dirty worktree"], 3)
        self.assertEqual(observed["status, idle repository"], 0)

    def test_the_same_assertion_still_admits_an_honest_effect_unknown_at_four(self) -> None:
        """The positive control, driven through the real ledger and the real choke point.

        `_report_failure`'s escalate-only rule is what makes 4 honest here: the refusal it is
        handed is a class-3 `refused`, and the ONLY reason the record comes back as 4 is that
        this invocation had already admitted an effect. So the same assertion that forbids a
        `effect: none` record from exiting 1 accepts this record at 4 -- it is judging the
        relationship between the document and the exit, not the number.
        """
        with ap._effect_ledger():
            ap._admit("created private directory transactions")
            result, code = ap._report_failure("apply", ap.ActivationError("refused", "Git worktree is not clean", 3), self.target)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["effect"], ap.EFFECT_UNKNOWN, result)
        self.assertEqual(result["admitted_effects"], ["created private directory transactions"], result)
        self.assertClassIsHonest(result, code, "escalated refusal over a non-empty ledger")
        # And the floor is one-directional: with nothing admitted the same refusal stays 3.
        with ap._effect_ledger():
            clean, clean_code = ap._report_failure("apply", ap.ActivationError("refused", "Git worktree is not clean", 3), self.target)
        self.assertEqual(clean_code, 3, clean)
        self.assertEqual(clean["effect"], ap.EFFECT_NONE, clean)
        self.assertClassIsHonest(clean, clean_code, "unescalated refusal over an empty ledger")

    def test_an_unresolvable_supplied_target_is_a_result_document_not_a_traceback(self) -> None:
        missing = Path(self.tmp.name) / "not-a-repo"
        for verb in (["status", "--target", str(missing)], ["recover", "inspect", "--target", str(missing)]):
            with self.subTest(verb=" ".join(verb)):
                completed = subprocess.run([sys.executable, str(SCRIPT), *verb], capture_output=True)
                # The measured defect: a raw FileNotFoundError walked out past every handler, so
                # the exit was 1 and stdout was EMPTY -- the one derivation point was bypassed.
                self.assertEqual(completed.returncode, 2, completed.stderr.decode())
                self.assertEqual(completed.stderr, b"")
                document = json.loads(completed.stdout)
                self.assertEqual(completed.stdout, ap.canonical_bytes(document))
                self.assertEqual(document["reasons"], ["cannot resolve the supplied target"])
                self.assertClassIsHonest(document, completed.returncode, " ".join(verb))
        # Positive control: the same surface on a target that DOES resolve still answers 0, so
        # the assertion above distinguishes two states rather than asserting one number.
        completed = subprocess.run([sys.executable, str(SCRIPT), "status", "--target", str(self.target)], capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        document = json.loads(completed.stdout)
        self.assertEqual(document["status"], "inactive")
        self.assertClassIsHonest(document, completed.returncode, "status on a resolvable target")

    def test_every_refusal_site_states_its_class_and_the_constructor_keeps_no_default(self) -> None:
        """The structural half: a default cannot be audited, so there must not be one.

        This is the test the `= 1` mutation kills on its own. The behavioural tests above only
        notice the default once some raise site also stops passing a class -- which is exactly
        the two-step regression this closes -- so the signature is pinned here directly.
        """
        tree = ast.parse(PLANNER.read_text())
        constructors = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "ActivationError"
            for node in node.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        ]
        self.assertEqual(len(constructors), 1)
        signature = constructors[0].args
        self.assertEqual([arg.arg for arg in signature.args], ["self", "status", "reason", "code"])
        self.assertEqual(signature.defaults, [], "code must stay positional-required: a defaulted class is an unauditable one")
        defaulted, explicit_one = [], []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            named = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if named not in {"ActivationError", "_UnresolvedTarget"}:
                continue
            supplied = node.args[2:3] or [keyword.value for keyword in node.keywords if keyword.arg == "code"]
            if not supplied:
                defaulted.append(node.lineno)
            elif isinstance(supplied[0], ast.Constant) and supplied[0].value == 1:
                explicit_one.append(node.lineno)
        self.assertEqual(defaulted, [], "every construction site states its own Decision 9 class")
        self.assertEqual(explicit_one, [], "1 is reserved for a failure this module never named")
        # A parameter default is invisible to the census above once a call site FORWARDS it
        # rather than stating a literal at the raise site itself: `_exact`'s `code` parameter
        # never appears as an `ast.Constant` argument to `ActivationError`, so the two loops
        # above see nothing to check. Every such forwarding function gets its own default
        # pinned here instead -- at minimum `_exact`'s `code: int = 2`.
        forwarding, non_constant_default, defaulted_to_one = [], [], []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            positional = node.args.posonlyargs + node.args.args
            index = next((i for i, arg in enumerate(positional) if arg.arg == "code"), None)
            if index is None:
                continue
            offset = len(positional) - len(node.args.defaults)
            if index < offset:
                continue  # `code` is required here, not defaulted -- outside this census
            forwards_code = False
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                named = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", None)
                if named not in {"ActivationError", "_UnresolvedTarget"}:
                    continue
                if any(isinstance(arg, ast.Name) and arg.id == "code" for arg in call.args):
                    forwards_code = True
                if any(kw.arg == "code" and isinstance(kw.value, ast.Name) and kw.value.id == "code" for kw in call.keywords):
                    forwards_code = True
            if not forwards_code:
                continue
            forwarding.append(node.name)
            default = node.args.defaults[index - offset]
            if not isinstance(default, ast.Constant):
                non_constant_default.append(node.name)
            elif default.value == 1:
                defaulted_to_one.append(node.name)
        self.assertIn("_exact", forwarding, "the known forwarding site must still be found by this census")
        self.assertEqual(non_constant_default, [], "a code parameter forwarded into ActivationError must default to a literal, not a derived value")
        self.assertEqual(defaulted_to_one, [], "1 is reserved for a failure this module never named")
        exact = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_exact")
        exact_positional = exact.args.posonlyargs + exact.args.args
        exact_index = next(i for i, arg in enumerate(exact_positional) if arg.arg == "code")
        exact_offset = len(exact_positional) - len(exact.args.defaults)
        exact_default = exact.args.defaults[exact_index - exact_offset]
        self.assertIsInstance(exact_default, ast.Constant)
        self.assertEqual(exact_default.value, 2, "_exact's forwarded default must stay pinned at 2")


if __name__ == "__main__":
    unittest.main()
