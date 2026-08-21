"""Tests for the WavePlan/PlanDiff compiler: its schemas, its input admission, its six checks, its IO.

Nine kinds of test live here and they check different things.

The SIBLING FIXTURES are built by RUNNING `mission-contract.py define` and `planning-snapshot.py
capture` once per test run, into one module-level scratch directory. Nothing here hand-writes a guess
of a sibling's sealed form: the whole point of admitting an input by re-deriving its digest is that a
hand-written approximation would either be rejected for the wrong reason or, worse, accepted while
the real sibling's output was not. Building the snapshot needs a real `git`, so the classes that
consume it skip with a named reason when git is absent; every class that does not need it runs
everywhere.

The ADMISSION and COMPILER-CHECK tests each carry a POSITIVE CONTROL: the unmutated input set is
asserted to reach `compiled` with NO reasons at all FIRST, so a test that stopped exercising its guard
would also have to stop reaching that state. A tolerated subset of reasons would let a guard rot
silently; `assert_compiled` tolerates none.

The COMPILER-CHECK classes are one per property -- provenance, authority bounds, graph, custody
exclusivity, capability feasibility, and resource bounds -- and each mutation is the smallest one that
violates only its own property. The graph class builds a 5000-workstream chain PROGRAMMATICALLY,
because the acyclicity walk is only provably iterative on an input a recursive one would kill.

The DIGEST ROUND-TRIP tests hand-seal a `wave-plan@1` and a `plan-diff@1` with this module's own
canonical helpers and hand them to `verify`, so the tool is proved to agree with the family's
published derivation rather than with itself. `--expect-digest` closes the loop a downstream
admission gate will actually use.

The INSTANT tests exist for one character class: the guard is `[0-9]`, not `\\d`, so an Arabic-Indic
digit string that `\\d` would happily accept must be refused. They also prove the guard runs BEFORE
any file is read, which is what makes "this tool reads no clock" checkable rather than aspirational.

The NON-FINITE tests put `1e400` at NESTED positions -- inside a list, and inside an object several
levels down -- because `parse_constant` never sees that literal: it is an ordinary JSON number that
overflows during parsing, and the post-parse walk is the only thing that catches it.

The DETERMINISM tests compare BYTES across two runs, and they vary the two ambient inputs a sealed
document must not depend on: `PYTHONHASHSEED`, which decides every `set` and `dict` iteration order in
the child, and the process directory. The hash-seed comparison carries its own positive control --
that the two seeds really do change this interpreter's string hashing -- because comparing two runs of
a tool whose randomization was disabled would prove nothing at all. They also assert the honest other
half: a relative `--out` IS resolved against the process directory, and that path is in the result
document rather than in either sealed one.

The AMBIENT-INPUT DISCIPLINE tests read both files with `ast` and assert the tool touches no `os`
attribute that reads ambient state, and that THIS module reaches for the environment only inside
`constructed_environment`. A substring search cannot do that job: the tool's docstring contains the
words `os.environ` in the sentence promising it does not appear.

The DECLARED-LIMIT tests pin what the tool says it does NOT check -- cross-kind custody overlap, the
demands no snapshot field observes, head freshness, and the nine unreachable change kinds -- and each
asserts a residual names its limit, so closing one has to update the residual in the same change.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "skills" / "agentic-sdlc" / "tools"
TOOL = TOOLS / "wave-plan-compiler.py"
MISSION_TOOL = TOOLS / "mission-contract.py"
SNAPSHOT_TOOL = TOOLS / "planning-snapshot.py"

MISSION_SCHEMA = "agentic-sdlc/mission-contract@1"
SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
SUBMISSIONS_SCHEMA = "agentic-sdlc/workstream-submissions@1"
PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
DIFF_SCHEMA = "agentic-sdlc/plan-diff@1"
LIMITS_SCHEMA = "agentic-sdlc/execution-profile-limits@1"
RESULT_SCHEMA = "agentic-sdlc/wave-plan-compiler-result@1"

COMPILED = "compiled"
VERIFIED = "verified"
REFUSED = "refused"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

AT = "2026-08-19T04:00:00Z"
MISSION_ID = "mission-slice-6"

DEFAULT_LIMITS = {"max_concurrent_nodes": 4, "max_total_nodes": 64, "recursive_spawn_generations": 0}

#: The diff vocabulary, re-expressed. Split into what a wave-plan@1 can actually produce a change of
#: and what it cannot, because the tool DECLARES the second half unreachable in its residuals and a
#: declared limit nobody checks is how the residual and the code drift apart.
CHANGE_KINDS = (
    "added-edge", "added-node", "approval", "artifact", "authority", "budget", "changed-node",
    "custody-boundary", "egress", "gate", "removed-edge", "removed-node", "retry", "route-constraint",
    "stop-rule", "terminal-criterion",
)
REACHABLE_KINDS = (
    "added-edge", "added-node", "authority", "changed-node", "custody-boundary", "removed-edge",
    "removed-node",
)

#: A `no_delta_reason` for a HAND-BUILT empty diff: the tool's cross-check admits any non-empty string,
#: and the exact sentence the tool itself writes is asserted by fragment where it is emitted, so this
#: constant cannot become the definition of what the tool says.
NO_DELTA = "these two revisions are identical, and this test wrote that sentence itself"

#: A head a hand-written plan can carry: a 40-character sha1 object name pair and a branch. The
#: compiled plans in this module carry the REAL captured snapshot's head instead, which is the point of
#: `test_the_compiled_plan_carries_the_snapshots_recorded_head_verbatim`.
FIXTURE_HEAD = {"branch": "trunk", "commit_sha": "a" * 40, "tree_sha": "b" * 40}

#: The tool reads no environment variable at all, so nothing needs scrubbing by name; every spawn
#: still CONSTRUCTS its environment from this function rather than passing `os.environ` through, so a
#: variable a future version began reading could not silently reach it from a developer's shell.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every spawn in this module hands a tool: an ALLOWLIST, not an inheritance."""
    environment = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    if extra:
        environment.update(extra)
    return environment


def canonical(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def expected_digest(sealed: dict[str, Any]) -> str:
    """The digest contract, re-expressed here so a drifted tool fails rather than agrees with itself.

    sha256 over `canonical(sealed minus the digest key)`. Re-expressed rather than imported: the tool
    has a hyphen in its name, so a plain `import` statement cannot name it, and a shared implementation
    would make this assertion vacuous.
    """
    body = {key: value for key, value in sealed.items() if key != "digest"}
    return hashlib.sha256(canonical(body)).hexdigest()


def seal(body: dict[str, Any]) -> dict[str, Any]:
    """Add the one derived key. This is how a test builds a document the tool will accept as sealed."""
    sealed = dict(body)
    sealed["digest"] = expected_digest(body)
    return sealed


def fake_digest(label: str) -> str:
    """A well-formed sha256 that stands for a document this test does not need to build."""
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


# ---- the sibling fixtures, built once per run ----------------------------------------------------

FIXTURES: dict[str, Any] = {}
_SCRATCH: tempfile.TemporaryDirectory[str] | None = None
NO_GIT = "a real git is required to capture a real PlanningSnapshot fixture"


def _run(argv: list[str], *, cwd: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv, capture_output=True, cwd=str(cwd), check=False, env=constructed_environment(extra)
    )


def _mission_body() -> dict[str, Any]:
    """One complete, valid MissionContract body in the shape `mission-contract.py` requires.

    Its ladder prefix and sorted stop-condition set are that tool's canonical forms; this body is an
    INPUT to it, and the sealed document the compiler admits is whatever that tool emits from it.
    """
    return {
        "schema": MISSION_SCHEMA,
        "mission_id": MISSION_ID,
        "objective": "close slice 6 by compiling one bounded wave from immutable planning artifacts",
        "scope": {
            "in_scope": ["skills/agentic-sdlc/tools/wave-plan-compiler.py", "tests/test_wave_plan_compiler.py"],
            "non_goals": ["the plan admission gate", "the drift classifier"],
        },
        "constraints": ["read-only and offline", "no clock: every instant is a caller-supplied input"],
        "authority": {
            "admitted_classes": ["read-only-advisory", "owned-worktree-write"],
            "ceiling": "owned-worktree-write",
        },
        "completion_contract": {
            "success_criteria": ["the digest re-derives from every sealed document"],
            "terminal_criteria": ["one named refusal for every inadmissible input"],
        },
        "stop_conditions": sorted(
            (
                "authority-expansion-required",
                "hard-stop-drift",
                "scope-change-required",
                "unknown-or-partial-effect",
            )
        ),
        "stated_at": "2026-08-19T03:00:00Z",
        "revision": 1,
        "supersedes": None,
    }


def setUpModule() -> None:
    """Build the two sibling fixtures ONCE, by running the real tools.

    A failure here is raised rather than skipped: a sibling that cannot seal its own valid input is a
    real regression, and swallowing it would silently delete this module's admission coverage.
    """
    global _SCRATCH
    _SCRATCH = tempfile.TemporaryDirectory(prefix="wave-plan-compiler-fixtures-")
    scratch = Path(_SCRATCH.name).resolve()
    FIXTURES["scratch"] = scratch

    body = scratch / "mission-body.json"
    body.write_text(json.dumps(_mission_body(), indent=2), encoding="utf-8")
    done = _run([sys.executable, "-B", str(MISSION_TOOL), "define", "--contract", str(body)], cwd=scratch)
    if done.returncode != EXIT_OK:
        raise AssertionError(f"mission-contract.py define failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != "defined":
        raise AssertionError(f"mission-contract.py refused a valid body: {result['reasons']}")
    mission = scratch / "mission.json"
    mission.write_bytes(canonical(result["contract"]))
    FIXTURES["mission"] = mission
    FIXTURES["mission_digest"] = result["digest"]

    if shutil.which("git") is None:
        return
    repository = scratch / "repo"
    repository.mkdir()
    git_environment = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for args in (
        ["init", "--quiet", "-b", "trunk", "."],
        ["add", "-A"],
    ):
        step = _run(["git", *args], cwd=repository, extra=git_environment)
        if step.returncode != 0:
            raise AssertionError(f"git {args} failed: {step.stderr!r}")
    (repository / "tracked.txt").write_text("one\n", encoding="utf-8")
    for args in (
        ["add", "tracked.txt"],
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", "one"],
    ):
        step = _run(["git", *args], cwd=repository, extra=git_environment)
        if step.returncode != 0:
            raise AssertionError(f"git {args} failed: {step.stderr!r}")
    snapshot = scratch / "snapshot.json"
    done = _run(
        [
            sys.executable, "-B", str(SNAPSHOT_TOOL), "capture",
            "--repository", str(repository), "--at", "2026-08-19T03:30:00Z", "--out", str(snapshot),
        ],
        cwd=scratch,
    )
    if done.returncode != EXIT_OK:
        raise AssertionError(f"planning-snapshot.py capture failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != "captured":
        raise AssertionError(f"planning-snapshot.py refused a real repository: {result['reasons']}")
    FIXTURES["repository"] = repository
    FIXTURES["snapshot"] = snapshot
    FIXTURES["snapshot_digest"] = result["digest"]


def tearDownModule() -> None:
    if _SCRATCH is not None:
        _SCRATCH.cleanup()


# ---- the documents this module owns --------------------------------------------------------------


def submissions_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid workstream-submissions@1 body: the control every negative case starts from.

    The workstreams are ordered by id and every list is a strictly ascending set, because those are the
    canonical forms the tool requires and this fixture must be in them to be a control.
    """
    body: dict[str, Any] = {
        "schema": SUBMISSIONS_SCHEMA,
        "submission_id": "submissions-slice-6-t5",
        "mission_id": MISSION_ID,
        "stated_at": "2026-08-19T03:45:00Z",
        "declared_concurrency": 2,
        "workstreams": [
            {
                "id": "ws-cartography",
                "objective": "map the planning artifact chain's existing tools and their digests",
                "authority_class": "read-only-advisory",
                "capability_demands": ["repository-read"],
                "dependencies": [],
                "file_custody": [],
                "worktree_custody": None,
            },
            {
                "id": "ws-compiler",
                "objective": "build the deterministic wave-plan compiler and its tests",
                "authority_class": "owned-worktree-write",
                "capability_demands": ["git-worktree-write", "python-execution"],
                "dependencies": ["ws-cartography"],
                "file_custody": [
                    "skills/agentic-sdlc/tools/wave-plan-compiler.py",
                    "tests/test_wave_plan_compiler.py",
                ],
                "worktree_custody": ".worktrees/wave-plan-compiler",
            },
        ],
    }
    body.update(overrides)
    return body


def plan_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid wave-plan@1 body, in every canonical order the tool re-derives."""
    body: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "compiled_at": AT,
        "mission_id": MISSION_ID,
        "revision": 1,
        "supersedes": None,
        "head": dict(FIXTURE_HEAD),
        "declared_concurrency": 2,
        "inputs": {
            "mission_digest": fake_digest("mission"),
            "snapshot_digest": fake_digest("snapshot"),
            "submissions_digest": fake_digest("submissions"),
        },
        "limits": dict(DEFAULT_LIMITS),
        "nodes": [
            {
                "node_id": "n-cartography",
                "objective": "map the existing planning tools",
                "authority_class": "read-only-advisory",
                "capability_demands": ["repository-read"],
                "dependencies": [],
                "file_custody": [],
                "worktree_custody": None,
                "output_schema": "agentic-sdlc/role-submission@1",
                "wrong_output_class": "derail",
            },
            {
                "node_id": "n-compiler",
                "objective": "build the compiler and its tests",
                "authority_class": "owned-worktree-write",
                "capability_demands": ["git-worktree-write", "python-execution"],
                "dependencies": ["n-cartography"],
                "file_custody": [
                    "skills/agentic-sdlc/tools/wave-plan-compiler.py",
                    "tests/test_wave_plan_compiler.py",
                ],
                "worktree_custody": ".worktrees/wave-plan-compiler",
                "output_schema": "agentic-sdlc/role-submission@1",
                "wrong_output_class": "degrade",
            },
        ],
        "edges": [{"from": "n-cartography", "to": "n-compiler"}],
    }
    body.update(overrides)
    return body


def diff_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid plan-diff@1 body for a FIRST wave: no prior plan, so nothing is removed."""
    body: dict[str, Any] = {
        "schema": DIFF_SCHEMA,
        "compiled_at": AT,
        "mission_id": MISSION_ID,
        "plan_digest": expected_digest(plan_body()),
        "prior_plan_digest": None,
        #: Null because this control NAMES changes. A diff may only carry a sentence here when its
        #: `changes` array is empty, and `EmptyDiffTests` covers both halves of that cross-check.
        "no_delta_reason": None,
        "changes": [
            {
                "kind": "added-edge",
                "subject": "n-cartography -> n-compiler",
                "evidence": "the submitted workstream ws-compiler declares ws-cartography as a dependency",
                "consequence": "n-compiler may not start until n-cartography's submission is recorded",
                "semantic": True,
            },
            {
                "kind": "added-node",
                "subject": "n-cartography",
                "evidence": "workstream ws-cartography, read-only-advisory",
                "consequence": "one advisory node is added to the wave and owns no worktree",
                "semantic": True,
            },
            {
                "kind": "added-node",
                "subject": "n-compiler",
                "evidence": "workstream ws-compiler, owned-worktree-write",
                "consequence": "one writing node is added to the wave",
                "semantic": True,
            },
            {
                "kind": "custody-boundary",
                "subject": "skills/agentic-sdlc/tools/wave-plan-compiler.py",
                "evidence": "declared file custody of workstream ws-compiler",
                "consequence": "no other node in this wave may write that path",
                "semantic": True,
            },
        ],
    }
    body.update(overrides)
    return body


class CompilerCase(unittest.TestCase):
    """Runs the tool in its own constructed scratch directory and parses its one result document."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name).resolve()

    def store(self, name: str, value: Any) -> Path:
        """Write one document to scratch. `indent=2` deliberately: the input's whitespace must not
        reach the digest, and a pretty-printed input is the cheapest proof of that."""
        path = self.work / f"{name}.json"
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def store_raw(self, name: str, raw: str) -> Path:
        path = self.work / f"{name}.json"
        path.write_text(raw, encoding="utf-8")
        return path

    def run_tool(
        self, *argv: str, extra: dict[str, str] | None = None, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        """`extra` and `cwd` exist for the determinism tests: an environment variable and a process
        directory are the two ambient inputs a sealed document must not depend on."""
        return _run([sys.executable, "-B", str(TOOL), *argv], cwd=cwd or self.work, extra=extra)

    def result(self, *argv: str, extra: dict[str, str] | None = None, cwd: Path | None = None) -> dict[str, Any]:
        done = self.run_tool(*argv, extra=extra, cwd=cwd)
        self.assertEqual(done.returncode, EXIT_OK, f"expected a delivered result, got {done.stderr!r}")
        document = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(document["schema"], RESULT_SCHEMA)
        self.assertEqual(canonical(document), done.stdout, "the result document is not in canonical form")
        return document

    def named(self, result: dict[str, Any], *fragments: str) -> None:
        """Assert the refusal names each fragment somewhere in its reasons."""
        self.assertEqual(result["verdict"], REFUSED, f"expected a refusal, got {result['reasons']}")
        joined = " || ".join(result["reasons"])
        for fragment in fragments:
            self.assertIn(fragment, joined)

    def verify_plan(self, sealed: dict[str, Any], *extra: str, name: str = "plan") -> dict[str, Any]:
        return self.result("verify", "--plan", str(self.store(name, sealed)), *extra)

    def verify_diff(self, sealed: dict[str, Any], *extra: str, name: str = "diff") -> dict[str, Any]:
        return self.result("verify", "--diff", str(self.store(name, sealed)), *extra)


class DigestRoundTripTests(CompilerCase):
    """Both output schemas round-trip through `verify`, sealed by this module rather than by the tool."""

    def test_a_hand_sealed_plan_verifies_and_republishes_its_digest(self) -> None:
        body = plan_body()
        sealed = seal(body)
        result = self.verify_plan(sealed)
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])
        self.assertEqual(result["plan_digest"], expected_digest(sealed))
        self.assertEqual(result["plan"], sealed)
        self.assertIsNone(result["diff"])
        self.assertIsNone(result["inputs_admitted"])

    def test_a_hand_sealed_diff_verifies_and_republishes_its_digest(self) -> None:
        sealed = seal(diff_body())
        result = self.verify_diff(sealed)
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])
        self.assertEqual(result["diff_digest"], expected_digest(sealed))
        self.assertEqual(result["diff"], sealed)
        self.assertIsNone(result["plan"])

    def test_expect_digest_binds_the_exact_document(self) -> None:
        sealed = seal(plan_body())
        digest = expected_digest(sealed)
        self.assertEqual(self.verify_plan(sealed, "--expect-digest", digest)["verdict"], VERIFIED)
        wrong = fake_digest("some other plan")
        self.named(self.verify_plan(sealed, "--expect-digest", wrong, name="again"), "--expect-digest", wrong)

    def test_an_edited_body_no_longer_derives_its_recorded_digest(self) -> None:
        sealed = seal(plan_body())
        self.assertEqual(self.verify_plan(sealed)["verdict"], VERIFIED)  # positive control
        edited = dict(sealed)
        edited["mission_id"] = "mission-something-else"
        self.named(self.verify_plan(edited, name="edited"), "does not re-derive")

    def test_a_digest_written_by_something_other_than_this_derivation_is_refused(self) -> None:
        body = plan_body()
        self.assertEqual(self.verify_plan(seal(body))["verdict"], VERIFIED)  # positive control
        forged = dict(body)
        # The whole document including a placeholder digest, which is NOT this family's derivation.
        forged["digest"] = hashlib.sha256(canonical(dict(body, digest="")) ).hexdigest()
        self.named(self.verify_plan(forged, name="forged"), "does not re-derive")

    def test_the_two_output_schemas_are_not_interchangeable(self) -> None:
        plan = seal(plan_body())
        diff = seal(diff_body())
        self.assertEqual(self.verify_plan(plan)["verdict"], VERIFIED)  # positive controls
        self.assertEqual(self.verify_diff(diff)["verdict"], VERIFIED)
        self.named(self.verify_plan(diff, name="diff-as-plan"), "closed sealed key set")
        self.named(self.verify_diff(plan, name="plan-as-diff"), "closed sealed key set")

    def test_verify_requires_exactly_one_artifact(self) -> None:
        sealed = self.store("plan", seal(plan_body()))
        self.assertEqual(self.run_tool("verify").returncode, EXIT_INPUT)
        both = self.run_tool("verify", "--plan", str(sealed), "--diff", str(sealed))
        self.assertEqual(both.returncode, EXIT_INPUT)
        self.assertEqual(b"", both.stdout, "a grammar error must not put bytes where the result lives")


class PlanShapeTests(CompilerCase):
    """Every closed field of a sealed wave-plan@1, each with the unmutated plan as its control."""

    def refuse(self, fragment: str, **overrides: Any) -> None:
        self.assertEqual(self.verify_plan(seal(plan_body()), name="control")["verdict"], VERIFIED)
        self.named(self.verify_plan(seal(plan_body(**overrides)), name="mutated"), fragment)

    def test_an_unknown_capability_demand_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[0]["capability_demands"] = ["telepathy"]
        self.refuse("telepathy", nodes=nodes)

    def test_an_authority_class_outside_the_ladder_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[0]["authority_class"] = "root"
        self.refuse("authority_class", nodes=nodes)

    def test_an_unknown_wrong_output_class_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1]["wrong_output_class"] = "catastrophe"
        self.refuse("wrong_output_class", nodes=nodes)

    def test_a_node_carrying_a_model_is_refused_as_an_unexpected_key(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1]["model"] = "some-exact-model-id"
        self.refuse("unexpected ['model']", nodes=nodes)

    def test_nodes_out_of_id_order_are_refused(self) -> None:
        nodes = list(reversed(plan_body()["nodes"]))
        self.refuse("not ordered by node_id", nodes=nodes)

    def test_a_repeated_node_id_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1] = dict(nodes[1], node_id="n-cartography", dependencies=[])
        self.refuse("more than once", nodes=nodes, edges=[])

    def test_edges_that_disagree_with_the_dependencies_are_refused(self) -> None:
        self.refuse("two different graphs", edges=[])

    def test_an_edge_naming_an_undeclared_node_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1]["dependencies"] = ["n-ghost"]
        self.refuse("points outside the graph", nodes=nodes, edges=[{"from": "n-ghost", "to": "n-compiler"}])

    def test_an_absolute_custody_path_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1]["file_custody"] = ["/etc/passwd"]
        self.refuse("is absolute", nodes=nodes)

    def test_a_dot_dot_custody_segment_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1]["worktree_custody"] = "../elsewhere"
        self.refuse("`..` segment", nodes=nodes)

    def test_a_backslash_custody_path_is_refused(self) -> None:
        # `a\..\..\etc` has no `/`-separated `..` segment at all, so the split-and-check below this
        # guard would never see one; the backslash has to be refused BEFORE that split runs.
        nodes = plan_body()["nodes"]
        nodes[1]["file_custody"] = [r"skills\wave-plan-compiler.py"]
        self.refuse("carries a backslash", nodes=nodes)

    def test_a_nul_character_in_a_custody_path_is_refused(self) -> None:
        # This tool owns the custody schema for both file_custody and worktree_custody, so the refusal
        # belongs here rather than in a sibling gate's own mirror of this rule.
        nodes = plan_body()["nodes"]
        nodes[1]["worktree_custody"] = "elsewhere\x00sneaky"
        self.refuse("carries a NUL character", nodes=nodes)

    def test_an_unsorted_file_custody_list_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        nodes[1]["file_custody"] = list(reversed(nodes[1]["file_custody"]))
        self.refuse("strictly ascending set", nodes=nodes)

    def test_a_duplicate_file_custody_entry_is_refused(self) -> None:
        nodes = plan_body()["nodes"]
        one = nodes[1]["file_custody"][0]
        nodes[1]["file_custody"] = sorted([*nodes[1]["file_custody"], one])
        self.refuse("strictly ascending set", nodes=nodes)

    def test_revision_one_may_not_supersede_a_plan(self) -> None:
        self.refuse("follows no prior plan", revision=1, supersedes=fake_digest("prior"))

    def test_a_later_revision_must_name_what_it_supersedes(self) -> None:
        self.refuse("names no superseded plan", revision=2, supersedes=None)

    def test_more_nodes_than_the_plans_own_ceiling_is_refused(self) -> None:
        self.refuse("contradicts itself", limits=dict(DEFAULT_LIMITS, max_total_nodes=1))

    def test_declared_concurrency_above_its_own_ceiling_is_refused(self) -> None:
        # Distinct from the node-count ceiling above: this is `declared_concurrency` against
        # `limits.max_concurrent_nodes`, the OTHER half of check_plan's self-contradiction guard.
        self.refuse("declares 5 concurrent nodes against its own recorded ceiling", declared_concurrency=5)

    def test_concurrency_above_the_total_ceiling_is_refused(self) -> None:
        self.refuse("can never be reached", limits=dict(DEFAULT_LIMITS, max_concurrent_nodes=99))

    def test_a_negative_recursion_generation_count_is_refused(self) -> None:
        self.refuse("recursive_spawn_generations", limits=dict(DEFAULT_LIMITS, recursive_spawn_generations=-1))

    def test_recursion_off_is_the_admitted_default_shape(self) -> None:
        # The positive control for the two limit refusals above: 0 generations is ADMITTED, so those
        # tests fail for their own reason rather than because any limits block is rejected.
        self.assertEqual(self.verify_plan(seal(plan_body()))["verdict"], VERIFIED)
        self.assertEqual(plan_body()["limits"]["recursive_spawn_generations"], 0)

    def test_a_missing_closed_key_is_named(self) -> None:
        body = plan_body()
        del body["edges"]
        sealed = seal(body)
        self.named(self.verify_plan(sealed, name="short"), "missing ['edges']")


class DiffShapeTests(CompilerCase):
    """Every closed field of a sealed plan-diff@1, each with the unmutated diff as its control."""

    def refuse(self, fragment: str, **overrides: Any) -> None:
        self.assertEqual(self.verify_diff(seal(diff_body()), name="control")["verdict"], VERIFIED)
        self.named(self.verify_diff(seal(diff_body(**overrides)), name="mutated"), fragment)

    def test_an_unknown_change_kind_is_refused(self) -> None:
        changes = diff_body()["changes"]
        changes[0] = dict(changes[0], kind="vibe-shift")
        self.refuse("kind", changes=changes)

    def test_a_first_wave_cannot_remove_or_change_a_node(self) -> None:
        changes = diff_body()["changes"]
        changes[0] = dict(changes[0], kind="removed-node", subject="n-gone")
        self.refuse("nothing for a first wave", changes=sorted(changes, key=lambda c: (c["kind"], c["subject"])))

    def test_a_removal_is_admitted_once_a_prior_plan_is_named(self) -> None:
        # The positive control for the test above: the same change kind is fine WITH a prior plan, so
        # that refusal is about the missing prior plan and not about the word "removed-node".
        changes = diff_body()["changes"]
        changes[0] = dict(changes[0], kind="removed-node", subject="n-gone")
        sealed = seal(
            diff_body(
                changes=sorted(changes, key=lambda change: (change["kind"], change["subject"])),
                prior_plan_digest=fake_digest("prior"),
            )
        )
        self.assertEqual(self.verify_diff(sealed)["verdict"], VERIFIED, self.verify_diff(sealed)["reasons"])

    def test_a_truthy_stand_in_for_semantic_is_refused(self) -> None:
        changes = diff_body()["changes"]
        changes[1] = dict(changes[1], semantic="yes")
        self.refuse("semantic is not a JSON boolean", changes=changes)

    def test_changes_out_of_canonical_order_are_refused(self) -> None:
        self.refuse("not ordered by (kind, subject)", changes=list(reversed(diff_body()["changes"])))

    def test_one_change_classified_twice_is_refused(self) -> None:
        changes = diff_body()["changes"]
        self.refuse(
            "more than once",
            changes=sorted(changes + [dict(changes[1])], key=lambda change: (change["kind"], change["subject"])),
        )

    def test_a_first_waves_diff_with_no_changes_is_refused(self) -> None:
        # A first wave adds its whole graph, so emptiness there is not "identical revisions": there is
        # no revision pair for it to be about. The empty diff `diff` emits always names a prior plan.
        self.refuse("no revision pair this emptiness could be about", changes=[], no_delta_reason=NO_DELTA)

    def test_a_hand_sealed_diff_naming_itself_as_its_own_prior_is_refused(self) -> None:
        # `compile --diff` refuses this pairing at synthesis time (`StandaloneDiffTests` covers that
        # half); this is the OTHER half -- a hand-sealed plan-diff@1 document that never went through
        # synthesis at all -- which is the shape `verify` alone must catch.
        body = diff_body()
        self.refuse("a plan superseding itself", prior_plan_digest=body["plan_digest"])


class InstantGuardTests(CompilerCase):
    """The `[0-9]` guard, and the fact that it runs before this tool opens anything."""

    def compile_with(self, at: str) -> subprocess.CompletedProcess[bytes]:
        absent = str(self.work / "absent.json")
        return self.run_tool(
            "compile", "--mission", absent, "--snapshot", absent, "--submissions", absent, "--at", at
        )

    def test_a_well_formed_instant_passes_the_guard_and_reaches_the_read(self) -> None:
        # The POSITIVE CONTROL for every refusal below, and the proof that the guard is a guard: with a
        # valid instant the run gets far enough to complain about the missing FILE instead.
        done = self.compile_with(AT)
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"mission contract", done.stderr)

    def test_an_arabic_indic_digit_instant_is_refused(self) -> None:
        # `\d` matches these; `[0-9]` does not, and that difference is the whole reason for the guard.
        done = self.compile_with("٢٠٢٦-08-19T04:00:00Z")
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"--at", done.stderr)
        self.assertNotIn(b"mission contract", done.stderr, "the clock guard must run before any read")

    def test_a_single_digit_month_is_refused(self) -> None:
        self.assertEqual(self.compile_with("2026-8-19T04:00:00Z").returncode, EXIT_INPUT)

    def test_a_local_instant_without_z_is_refused(self) -> None:
        self.assertEqual(self.compile_with("2026-08-19T04:00:00").returncode, EXIT_INPUT)

    def test_a_trailing_suffix_is_refused(self) -> None:
        self.assertEqual(self.compile_with(AT + " and later").returncode, EXIT_INPUT)

    def test_an_instant_recorded_in_a_plan_is_held_to_the_same_guard(self) -> None:
        self.assertEqual(self.verify_plan(seal(plan_body()), name="control")["verdict"], VERIFIED)
        self.named(
            self.verify_plan(seal(plan_body(compiled_at="٢٠٢٦-08-19T04:00:00Z")), name="unicode"),
            "compiled_at",
        )


class NonFiniteTests(CompilerCase):
    """`1e400` at nested positions, which `parse_constant` never sees, plus the announced spellings."""

    def unusable(self, raw: str, name: str) -> bytes:
        done = self.run_tool("verify", "--plan", str(self.store_raw(name, raw)))
        self.assertEqual(done.returncode, EXIT_INPUT, f"expected unusable input, got {done.stdout!r}")
        self.assertEqual(b"", done.stdout, "an unusable input must not put bytes where the result lives")
        return done.stderr

    def test_an_overflowing_literal_inside_a_list_is_refused_by_position(self) -> None:
        sealed = seal(plan_body())
        raw = canonical(sealed).decode("ascii").replace('"limits":{', '"overflow":[0,1e400],"limits":{', 1)
        self.assertIn(b"non-finite", self.unusable(raw, "in-list"))

    def test_an_overflowing_literal_nested_in_an_object_is_refused(self) -> None:
        body = plan_body()
        body["nodes"][1]["objective"] = "PLACEHOLDER"
        raw = canonical(seal(body)).decode("ascii").replace('"PLACEHOLDER"', '{"deep":{"deeper":[{"worse":1e400}]}}', 1)
        self.assertIn(b"non-finite", self.unusable(raw, "in-object"))

    def test_the_announced_constants_are_refused_by_name(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity"):
            raw = canonical(seal(plan_body())).decode("ascii").replace('"revision":1', f'"revision":{token}', 1)
            self.assertIn(token.encode("ascii"), self.unusable(raw, f"token-{token}"))

    def test_a_finite_number_in_the_same_position_is_admitted(self) -> None:
        # The POSITIVE CONTROL: the same surgery with an ordinary number reaches a RESULT, so the tests
        # above fail on the non-finite value and not on the edit itself.
        raw = canonical(seal(plan_body())).decode("ascii").replace('"revision":1', '"revision":1e2', 1)
        done = self.run_tool("verify", "--plan", str(self.store_raw("finite", raw)))
        self.assertEqual(done.returncode, EXIT_OK)
        self.named(json.loads(done.stdout.decode("utf-8")), "revision")

    def test_a_repeated_json_key_is_refused_rather_than_resolved(self) -> None:
        raw = canonical(seal(plan_body())).decode("ascii").replace('"revision":1', '"revision":1,"revision":2', 1)
        self.assertIn(b"repeats the JSON key", self.unusable(raw, "repeated"))


class ModuleDisciplineTests(unittest.TestCase):
    """The clock-free, subprocess-free, import-free claims, read with `ast` rather than by grep.

    A substring search would be fooled by prose: the module's own docstring contains the words
    "subprocess-free" and "reads no clock", so a `assertNotIn` over the source would fail on the
    promise itself.
    """

    def setUp(self) -> None:
        self.tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        self.imported: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                self.imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.imported.add(node.module.split(".")[0])

    def test_the_extractor_sees_the_imports_that_are_there(self) -> None:
        # The positive control for the two assertions below.
        self.assertLessEqual({"hashlib", "json", "argparse"}, self.imported)

    def test_no_clock_and_no_subprocess_is_imported(self) -> None:
        for forbidden in ("time", "datetime", "subprocess", "socket", "urllib", "random"):
            self.assertNotIn(forbidden, self.imported, f"{forbidden} contradicts this tool's own claims")

    def test_no_sibling_tool_is_imported(self) -> None:
        for name in self.imported:
            self.assertNotIn("mission", name)
            self.assertNotIn("planning", name)

    def test_the_tool_is_only_stdlib(self) -> None:
        allowed = {
            "__future__", "argparse", "collections", "hashlib", "json", "math", "os", "pathlib", "re",
            "stat", "sys", "typing",
        }
        self.assertLessEqual(self.imported, allowed, f"unexpected imports: {sorted(self.imported - allowed)}")


class AdmissionCase(CompilerCase):
    """Compiles with the REAL sibling fixtures, so every admission assertion is about a real document.

    Skipped by name rather than silently when the PlanningSnapshot fixture could not be captured: a
    class that quietly passed with no snapshot would be reporting coverage it does not have.
    """

    def setUp(self) -> None:
        super().setUp()
        if "snapshot" not in FIXTURES:
            self.skipTest(NO_GIT)

    def compile_result(
        self,
        *,
        mission: Path | None = None,
        snapshot: Path | None = None,
        submissions: Path | dict[str, Any] | None = None,
        extra: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if submissions is None:
            submissions = self.store("submissions", seal(submissions_body()))
        elif isinstance(submissions, dict):
            submissions = self.store("submissions", seal(submissions))
        return self.result(
            "compile",
            "--mission", str(mission or FIXTURES["mission"]),
            "--snapshot", str(snapshot or FIXTURES["snapshot"]),
            "--submissions", str(submissions),
            "--at", AT,
            *extra,
        )

    def assert_compiled(self, result: dict[str, Any]) -> dict[str, Any]:
        """THE positive control for every refusal in this module: this input set COMPILES.

        Asserted with NO reasons at all rather than with a tolerated subset, so a test whose guard
        stopped firing would also have to stop reaching this state. Returns the sealed plan, which is
        also the assertion that a compiled verdict publishes one.
        """
        self.assertEqual(result["verdict"], COMPILED, result["reasons"])
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["inputs_admitted"])
        self.assertIsNotNone(result["plan"])
        self.assertIsNotNone(result["diff"])
        return result["plan"]

    def mission_bound_plan(self, **overrides: Any) -> dict[str, Any]:
        """A hand-built sealed plan bound to the REAL mission fixture's digest.

        A prior plan must bind the same mission contract as the compilation that supersedes it, so a
        hand-built one carrying `fake_digest("mission")` is refused by the pin rather than admitted --
        which is exactly what `test_a_prior_plan_bound_to_another_mission_is_refused` asserts, and why
        every other prior-plan case has to bind the real digest to be about anything else.
        """
        inputs = dict(plan_body()["inputs"], mission_digest=FIXTURES["mission_digest"])
        return seal(plan_body(inputs=inputs, **overrides))

    def resealed(self, name: str, path: Path, mutate: Any) -> Path:
        """A sibling's real document, mutated and RE-SEALED, so exactly one thing is wrong with it."""
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        document.pop("digest", None)
        mutate(document)
        return self.store(name, seal(document))

    def tampered(self, name: str, path: Path, mutate: Any) -> Path:
        """A sibling's real document, mutated with its ORIGINAL digest left in place."""
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        mutate(document)
        return self.store(name, document)


class InputAdmissionTests(AdmissionCase):
    """One named refusal per inadmissible input, each against the fully admitted set as its control."""

    def test_the_admitted_input_set_compiles_and_the_plan_binds_its_three_inputs(self) -> None:
        submissions = seal(submissions_body())
        result = self.compile_result(submissions=submissions)
        plan = self.assert_compiled(result)
        self.assertEqual(
            result["inputs"],
            {
                "mission_digest": FIXTURES["mission_digest"],
                "prior_plan_digest": None,
                "snapshot_digest": FIXTURES["snapshot_digest"],
                "submissions_digest": expected_digest(submissions),
            },
        )
        self.assertEqual(result["limits"], DEFAULT_LIMITS, "the handoff's defaults apply without --limits")
        # The provenance binding, read off the SEALED plan rather than off the result's own summary.
        self.assertEqual(
            plan["inputs"],
            {
                "mission_digest": FIXTURES["mission_digest"],
                "snapshot_digest": FIXTURES["snapshot_digest"],
                "submissions_digest": expected_digest(submissions),
            },
        )
        self.assertEqual(plan["limits"], DEFAULT_LIMITS, "the plan records the limits it was compiled under")
        self.assertEqual(plan["digest"], expected_digest(plan), "the plan does not re-derive its own digest")
        self.assertEqual(result["plan_digest"], plan["digest"])
        self.assertEqual(result["diff"]["plan_digest"], plan["digest"], "the diff must name the plan it describes")

    def test_a_mission_declaring_another_schema_is_refused_by_name(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        wrong = self.resealed("wrong-mission", FIXTURES["mission"], lambda doc: doc.update(schema=SNAPSHOT_SCHEMA))
        self.named(self.compile_result(mission=wrong), "the mission contract declares schema", MISSION_SCHEMA)

    def test_a_mission_whose_content_does_not_derive_its_digest_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        edited = self.tampered("edited-mission", FIXTURES["mission"], lambda doc: doc.update(mission_id="mission-x"))
        self.named(self.compile_result(mission=edited), "the mission contract records digest", "does not re-derive")

    def test_a_mission_missing_a_consumed_field_is_refused_by_dotted_name(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        short = self.resealed("short-mission", FIXTURES["mission"], lambda doc: doc["authority"].pop("ceiling"))
        self.named(self.compile_result(mission=short), "has no authority.ceiling")

    def test_a_snapshot_declaring_another_schema_is_refused_by_name(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        wrong = self.resealed("wrong-snapshot", FIXTURES["snapshot"], lambda doc: doc.update(schema=MISSION_SCHEMA))
        self.named(self.compile_result(snapshot=wrong), "the planning snapshot declares schema", SNAPSHOT_SCHEMA)

    def test_a_snapshot_whose_content_does_not_derive_its_digest_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        edited = self.tampered(
            "edited-snapshot", FIXTURES["snapshot"], lambda doc: doc["dirty_state"].update(untracked=99)
        )
        self.named(self.compile_result(snapshot=edited), "the planning snapshot records digest")

    def test_a_snapshot_missing_the_head_this_compiler_consumes_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        short = self.resealed("short-snapshot", FIXTURES["snapshot"], lambda doc: doc["head"].pop("commit_sha"))
        self.named(self.compile_result(snapshot=short), "has no head.commit_sha")

    def test_the_two_sibling_documents_are_not_interchangeable(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        swapped = self.compile_result(mission=FIXTURES["snapshot"], snapshot=FIXTURES["mission"])
        self.named(swapped, "the mission contract declares schema", "the planning snapshot declares schema")

    def test_a_submissions_document_declaring_another_schema_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        self.named(
            self.compile_result(submissions=submissions_body(schema=PLAN_SCHEMA)),
            "the workstream submissions declares schema",
        )

    def test_a_submissions_document_missing_a_closed_key_is_refused(self) -> None:
        body = submissions_body()
        del body["submission_id"]
        self.named(self.compile_result(submissions=body), "missing ['submission_id']")

    def test_an_unknown_capability_demand_is_refused_against_the_closed_set(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        streams = submissions_body()["workstreams"]
        streams[0]["capability_demands"] = ["mind-reading"]
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "mind-reading")

    def test_a_workstream_demanding_no_capability_is_refused(self) -> None:
        streams = submissions_body()["workstreams"]
        streams[0]["capability_demands"] = []
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "is empty")

    def test_an_authority_class_outside_the_ladder_is_refused(self) -> None:
        streams = submissions_body()["workstreams"]
        streams[1]["authority_class"] = "sudo"
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "authority_class")

    def test_an_absolute_worktree_custody_path_is_refused(self) -> None:
        streams = submissions_body()["workstreams"]
        streams[1]["worktree_custody"] = "/tmp/somewhere"
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "is absolute")

    def test_a_repeated_workstream_id_is_refused(self) -> None:
        streams = submissions_body()["workstreams"]
        streams[1]["id"] = streams[0]["id"]
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "more than once")

    def test_workstreams_out_of_id_order_are_refused(self) -> None:
        streams = list(reversed(submissions_body()["workstreams"]))
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "not ordered by id")

    def test_a_submissions_document_with_no_workstream_is_refused(self) -> None:
        self.named(self.compile_result(submissions=submissions_body(workstreams=[])), "proposes nothing")

    def test_a_workstream_id_carrying_whitespace_is_refused(self) -> None:
        streams = submissions_body()["workstreams"]
        streams[0]["id"] = "ws cartography"
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "not an identifier")

    def test_an_unreadable_input_is_unusable_rather_than_refused(self) -> None:
        absent = self.work / "nowhere.json"
        done = self.run_tool(
            "compile",
            "--mission", str(absent),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", str(self.store("submissions", seal(submissions_body()))),
            "--at", AT,
        )
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(b"", done.stdout, "an unusable input must not put bytes where the result lives")
        self.assertIn(b"mission contract", done.stderr)

    def test_a_directory_supplied_as_a_document_is_unusable(self) -> None:
        done = self.run_tool(
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(self.work),
            "--submissions", str(self.store("submissions", seal(submissions_body()))),
            "--at", AT,
        )
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"not a regular file", done.stderr)


class PriorPlanAdmissionTests(AdmissionCase):
    """The optional prior revision: absent means first wave, present means a full plan shape check."""

    def test_a_sealed_prior_plan_becomes_the_next_revision_rather_than_being_edited(self) -> None:
        sealed = self.mission_bound_plan()
        prior = self.store("prior", sealed)
        result = self.compile_result(extra=("--prior-plan", str(prior)))
        plan = self.assert_compiled(result)
        self.assertEqual(result["inputs"]["prior_plan_digest"], expected_digest(sealed))
        self.assertEqual(plan["revision"], 2, "a revision takes the next number")
        self.assertEqual(plan["supersedes"], expected_digest(sealed), "and names exactly what it supersedes")
        self.assertEqual(result["diff"]["prior_plan_digest"], expected_digest(sealed))
        # The prior plan's nodes are named nothing like the submitted workstreams, so the delta is the
        # whole graph replaced: two nodes added, two removed, and the prior edge gone.
        kinds = sorted({change["kind"] for change in result["diff"]["changes"]})
        self.assertEqual(
            kinds,
            ["added-edge", "added-node", "authority", "custody-boundary", "removed-edge", "removed-node"],
        )

    def test_a_malformed_prior_plan_is_refused_against_its_own_input_position(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        broken = self.store("prior", seal(plan_body(edges=[])))
        result = self.compile_result(extra=("--prior-plan", str(broken)))
        self.named(result, "two different graphs")
        slugs = {check["slug"] for check in result["checks"] if not check["met"]}
        self.assertIn("prior-plan", slugs, "a prior plan's shape must be reported where it arrived")

    def test_a_diff_supplied_as_a_prior_plan_is_refused_by_schema(self) -> None:
        diff = self.store("prior", seal(diff_body()))
        self.named(
            self.compile_result(extra=("--prior-plan", str(diff))), "the prior wave plan declares schema"
        )


class ExecutionProfileTests(AdmissionCase):
    """`--limits` is repository POLICY: a closed object, no digest, and defaults when it is absent."""

    def profile(self, **overrides: Any) -> Path:
        document = {"schema": LIMITS_SCHEMA, **DEFAULT_LIMITS}
        document.update(overrides)
        return self.store("limits", document)

    def test_a_supplied_profile_is_admitted_and_republished(self) -> None:
        result = self.compile_result(extra=("--limits", str(self.profile(max_concurrent_nodes=2))))
        self.assert_compiled(result)
        self.assertEqual(result["limits"], dict(DEFAULT_LIMITS, max_concurrent_nodes=2))

    def test_a_profile_declaring_another_schema_is_refused(self) -> None:
        self.assert_compiled(self.compile_result(extra=("--limits", str(self.profile()))))  # positive control
        self.named(
            self.compile_result(extra=("--limits", str(self.profile(schema=PLAN_SCHEMA)))),
            "the execution profile declares schema",
        )

    def test_a_profile_carrying_a_digest_is_refused_as_an_unexpected_key(self) -> None:
        self.named(
            self.compile_result(extra=("--limits", str(self.profile(digest=fake_digest("policy"))))),
            "unexpected ['digest']",
        )

    def test_a_zero_node_ceiling_is_refused(self) -> None:
        self.named(self.compile_result(extra=("--limits", str(self.profile(max_total_nodes=0)))), "at least 1")

    def test_a_boolean_ceiling_is_refused_rather_than_read_as_one(self) -> None:
        self.named(
            self.compile_result(extra=("--limits", str(self.profile(max_concurrent_nodes=True)))), "at least 1"
        )

    def test_concurrency_above_the_total_ceiling_is_refused(self) -> None:
        self.named(
            self.compile_result(extra=("--limits", str(self.profile(max_concurrent_nodes=100)))),
            "can never be reached",
        )


class OutputPathTests(AdmissionCase):
    """`--out`/`--diff-out`: the exclusive write, and every refusal that happens before it."""

    def outside(self, name: str) -> Path:
        """A destination outside the snapshot's repository: the module scratch, not the repository."""
        return self.work / name

    def test_two_fresh_destinations_receive_the_exact_sealed_documents(self) -> None:
        out, diff_out = self.outside("plan.json"), self.outside("diff.json")
        result = self.compile_result(extra=("--out", str(out), "--diff-out", str(diff_out)))
        plan = self.assert_compiled(result)  # the POSITIVE CONTROL for every refusal below
        self.assertEqual(result["out"], str(out))
        self.assertEqual(result["diff_out"], str(diff_out))
        # Byte-identical, not merely equal-when-parsed: the file a later gate digests is these bytes.
        self.assertEqual(out.read_bytes(), canonical(plan))
        self.assertEqual(diff_out.read_bytes(), canonical(result["diff"]))

    def test_diff_out_without_out_writes_an_unpaired_diff_at_exit_zero(self) -> None:
        # A recorded observation, not a refusal: pairing the two files is the caller's request to
        # make, and this run's diff still names a plan_digest for a plan it never put on disk.
        diff_out = self.outside("diff.json")
        result = self.compile_result(extra=("--diff-out", str(diff_out)))
        self.assert_compiled(result)
        self.assertEqual(result["exit_code"], EXIT_OK)
        self.assertIsNone(result["out"])
        self.assertEqual(result["diff_out"], str(diff_out))
        self.assertEqual(diff_out.read_bytes(), canonical(result["diff"]))
        self.assertEqual(result["diff"]["plan_digest"], result["plan"]["digest"])
        self.assertIn("--diff-out may be supplied without --out", " || ".join(result["residuals"]))

    def test_a_refused_compilation_writes_neither_document(self) -> None:
        out, diff_out = self.outside("plan.json"), self.outside("diff.json")
        streams = submissions_body()["workstreams"]
        streams[1]["dependencies"] = ["ws-nobody-submitted"]
        result = self.compile_result(
            submissions=submissions_body(workstreams=streams),
            extra=("--out", str(out), "--diff-out", str(diff_out)),
        )
        self.named(result, "ws-nobody-submitted")
        self.assertIsNone(result["out"])
        self.assertIsNone(result["diff_out"])
        self.assertFalse(out.exists(), "a refused compilation writes nothing")
        self.assertFalse(diff_out.exists(), "a refused compilation writes nothing")

    def test_a_written_plan_verifies_through_the_tools_own_verify_verb(self) -> None:
        """The round trip that matters: what `compile` seals is what `verify` re-derives."""
        out, diff_out = self.outside("plan.json"), self.outside("diff.json")
        result = self.compile_result(extra=("--out", str(out), "--diff-out", str(diff_out)))
        plan = self.assert_compiled(result)
        verified = self.result("verify", "--plan", str(out), "--expect-digest", plan["digest"])
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])
        verified_diff = self.result("verify", "--diff", str(diff_out))
        self.assertEqual(verified_diff["verdict"], VERIFIED, verified_diff["reasons"])

    def test_an_occupied_destination_is_refused_rather_than_replaced(self) -> None:
        out = self.outside("plan.json")
        out.write_text("do not lose me\n", encoding="utf-8")
        self.named(self.compile_result(extra=("--out", str(out))), "already exists", "refused rather than replaced")
        self.assertEqual("do not lose me\n", out.read_text(encoding="utf-8"))

    def test_a_destination_inside_the_snapshots_worktree_is_refused(self) -> None:
        inside = Path(FIXTURES["repository"]) / "plan.json"
        result = self.compile_result(extra=("--out", str(inside)))
        self.named(result, "resolves inside the snapshot's observed", "dirty state")
        self.assertFalse(inside.exists())

    def test_a_destination_below_the_snapshots_worktree_is_refused(self) -> None:
        nested = Path(FIXTURES["repository"]) / "nested"
        nested.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, nested, True)
        self.named(
            self.compile_result(extra=("--diff-out", str(nested / "diff.json"))),
            "resolves inside the snapshot's observed",
        )

    def test_containment_is_measured_through_a_symlinked_parent(self) -> None:
        """Lexical containment would be defeated by a link, so the caller-side parent is resolved.

        Only the `--out` argument's parent is `realpath`-resolved before the containment comparison;
        the snapshot-recorded worktree path is compared as recorded.
        """
        link = self.work / "elsewhere"
        try:
            link.symlink_to(FIXTURES["repository"], target_is_directory=True)
        except OSError:  # a host without symlink permission cannot ask this question
            self.skipTest("this host does not permit creating a symlink")
        result = self.compile_result(extra=("--out", str(link / "plan.json")))
        self.named(result, "resolves inside the snapshot's observed")
        self.assertFalse((Path(FIXTURES["repository"]) / "plan.json").exists())

    def test_a_destination_with_no_existing_parent_is_refused(self) -> None:
        self.named(
            self.compile_result(extra=("--out", str(self.outside("missing") / "plan.json"))),
            "no existing directory",
        )

    def test_one_path_for_both_documents_is_refused(self) -> None:
        both = str(self.outside("one.json"))
        self.named(self.compile_result(extra=("--out", both, "--diff-out", both)), "name the same path")

    def test_a_refused_destination_still_publishes_the_admitted_input_digests(self) -> None:
        """An output destination is not an input, so refusing one must not hide what WAS admitted."""
        submissions = seal(submissions_body())
        occupied = self.outside("plan.json")
        occupied.write_text("occupied\n", encoding="utf-8")
        result = self.compile_result(submissions=submissions, extra=("--out", str(occupied)))
        self.named(result, "already exists")
        self.assertTrue(result["inputs_admitted"])
        self.assertEqual(result["inputs"]["submissions_digest"], expected_digest(submissions))
        # The negative half of the same fact: a refused INPUT does hide them.
        broken = self.compile_result(submissions=submissions_body(workstreams=[]))
        self.assertFalse(broken["inputs_admitted"])
        self.assertIsNone(broken["inputs"])


# ---- the six compiler checks ---------------------------------------------------------------------


def workstream(
    identifier: str,
    *,
    authority_class: str = "read-only-advisory",
    demands: tuple[str, ...] = ("repository-read",),
    dependencies: tuple[str, ...] = (),
    files: tuple[str, ...] = (),
    worktree: str | None = None,
) -> dict[str, Any]:
    """One well-formed workstream, so a compiler-check test mutates ONE property and nothing else."""
    return {
        "id": identifier,
        "objective": f"the bounded objective of {identifier}",
        "authority_class": authority_class,
        "capability_demands": sorted(demands),
        "dependencies": sorted(dependencies),
        "file_custody": sorted(files),
        "worktree_custody": worktree,
    }


def chain_submissions(count: int, *, close_the_loop: bool = False) -> dict[str, Any]:
    """A PROGRAMMATICALLY built dependency chain, which is the only honest test of an iterative walk.

    `close_the_loop` makes the first workstream depend on the last, turning the same chain into one
    enormous cycle: the acyclicity refusal has to survive the same depth the admission does.
    """
    names = [f"ws-{index:05d}" for index in range(count)]
    workstreams = [
        workstream(
            name,
            dependencies=() if index == 0 else (names[index - 1],),
            files=(f"src/{name}.py",),
        )
        for index, name in enumerate(names)
    ]
    if close_the_loop:
        workstreams[0]["dependencies"] = [names[-1]]
    return submissions_body(workstreams=workstreams, declared_concurrency=1)


class ProvenanceTests(AdmissionCase):
    """The three digests, the limits, and the snapshot's head carried VERBATIM into the plan."""

    def test_the_compiled_plan_carries_the_snapshots_recorded_head_verbatim(self) -> None:
        plan = self.assert_compiled(self.compile_result())
        recorded = json.loads(Path(FIXTURES["snapshot"]).read_text(encoding="utf-8"))["head"]
        self.assertEqual(plan["head"], recorded, "the plan's head is not the snapshot's own record")

    def test_head_freshness_is_not_this_tools_judgment(self) -> None:
        """A head no repository ever had still compiles: this tool runs no git and compares nothing.

        Freshness is the plan-admission gate's check. If this test ever starts failing because the
        compiler grew a comparison, that comparison is in the wrong tool.
        """
        invented = {"branch": "trunk", "commit_sha": "c" * 40, "tree_sha": "d" * 40}
        snapshot = self.resealed("head-moved", FIXTURES["snapshot"], lambda doc: doc.update(head=invented))
        plan = self.assert_compiled(self.compile_result(snapshot=snapshot))
        self.assertEqual(plan["head"], invented)

    def test_submissions_made_for_another_mission_are_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        self.named(
            self.compile_result(submissions=submissions_body(mission_id="mission-something-else")),
            "were made for a different mission",
        )

    def test_a_head_with_an_unknown_key_cannot_be_carried_verbatim(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        snapshot = self.resealed(
            "head-extra", FIXTURES["snapshot"], lambda doc: doc["head"].update(shallow=False)
        )
        self.named(self.compile_result(snapshot=snapshot), "cannot be carried verbatim")

    def test_a_head_that_is_not_a_git_object_name_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        snapshot = self.resealed(
            "head-short", FIXTURES["snapshot"], lambda doc: doc["head"].update(commit_sha="abc123")
        )
        self.named(self.compile_result(snapshot=snapshot), "head.commit_sha", "git object name")

    def test_a_detached_head_is_admitted_and_carried_as_null(self) -> None:
        # The positive control for the branch guard: null is how a detached head is stated, not an error.
        snapshot = self.resealed("detached", FIXTURES["snapshot"], lambda doc: doc["head"].update(branch=None))
        plan = self.assert_compiled(self.compile_result(snapshot=snapshot))
        self.assertIsNone(plan["head"]["branch"])


class AuthorityBoundsTests(AdmissionCase):
    """The mission's ladder prefix and ceiling, against every workstream's declared class."""

    def wider_mission(self, ceiling: str, admitted: list[str]) -> Path:
        return self.resealed(
            "wider-mission",
            FIXTURES["mission"],
            lambda doc: doc["authority"].update(admitted_classes=admitted, ceiling=ceiling),
        )

    def test_a_class_the_mission_does_not_admit_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        streams = submissions_body()["workstreams"]
        streams[1]["authority_class"] = "authorized-fan-in"
        self.named(
            self.compile_result(submissions=submissions_body(workstreams=streams)),
            "does not admit",
            "cannot grant an authority its mission never did",
        )

    def test_an_admitted_class_above_the_ceiling_is_refused(self) -> None:
        ladder = ["read-only-advisory", "owned-worktree-write", "authorized-fan-in"]
        mission = self.wider_mission("owned-worktree-write", ladder)
        self.assert_compiled(self.compile_result(mission=mission))  # positive control
        streams = submissions_body()["workstreams"]
        streams[1]["authority_class"] = "authorized-fan-in"
        result = self.compile_result(mission=mission, submissions=submissions_body(workstreams=streams))
        self.named(result, "above the mission's ceiling")

    def test_a_class_at_the_ceiling_is_admitted(self) -> None:
        # The positive control for the test above: the ceiling itself is IN bounds, so that refusal is
        # about being above it rather than about naming it.
        ladder = ["read-only-advisory", "owned-worktree-write", "authorized-fan-in"]
        mission = self.wider_mission("authorized-fan-in", ladder)
        streams = submissions_body()["workstreams"]
        streams[1]["authority_class"] = "authorized-fan-in"
        plan = self.assert_compiled(
            self.compile_result(mission=mission, submissions=submissions_body(workstreams=streams))
        )
        self.assertEqual(plan["nodes"][1]["authority_class"], "authorized-fan-in")

    def test_admitted_classes_that_are_not_a_ladder_prefix_are_refused(self) -> None:
        mission = self.wider_mission("authorized-fan-in", ["read-only-advisory", "authorized-fan-in"])
        self.named(self.compile_result(mission=mission), "is not a prefix of the ladder")

    def test_a_ceiling_outside_the_admitted_classes_is_refused(self) -> None:
        mission = self.wider_mission("outward-effect", ["read-only-advisory", "owned-worktree-write"])
        self.named(self.compile_result(mission=mission), "is not one of the classes it admits")


class GraphTests(AdmissionCase):
    """Dependencies that resolve, no self-dependency, no duplicate id, and an ITERATIVE acyclicity walk."""

    def test_a_dependency_on_an_unsubmitted_workstream_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        streams = submissions_body()["workstreams"]
        streams[1]["dependencies"] = ["ws-imaginary"]
        self.named(
            self.compile_result(submissions=submissions_body(workstreams=streams)),
            "ws-imaginary",
            "can never be satisfied",
        )

    def test_a_self_dependency_is_refused(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control
        streams = submissions_body()["workstreams"]
        streams[1]["dependencies"] = [streams[1]["id"]]
        self.named(
            self.compile_result(submissions=submissions_body(workstreams=streams)),
            "its own dependency",
        )

    def test_a_two_workstream_cycle_is_refused(self) -> None:
        streams = [
            workstream("ws-alpha", dependencies=("ws-beta",), files=("a.py",)),
            workstream("ws-beta", dependencies=("ws-alpha",), files=("b.py",)),
        ]
        result = self.compile_result(submissions=submissions_body(workstreams=streams))
        self.named(result, "cyclic", "['ws-alpha', 'ws-beta']")

    def test_the_same_two_workstreams_without_the_cycle_compile(self) -> None:
        # The positive control for the cycle refusal: one direction of the same pair is a legal graph.
        streams = [
            workstream("ws-alpha", files=("a.py",)),
            workstream("ws-beta", dependencies=("ws-alpha",), files=("b.py",)),
        ]
        plan = self.assert_compiled(self.compile_result(submissions=submissions_body(workstreams=streams)))
        self.assertEqual(plan["edges"], [{"from": "ws-alpha", "to": "ws-beta"}])

    def test_a_duplicate_workstream_id_stops_every_later_check(self) -> None:
        """One repeated id is ONE reason: two workstreams under one name make every custody,
        dependency, and authority statement ambiguous about WHICH of them it belongs to, so the compiler
        checks do not run at all over a submissions document that already has a reason of its own.

        The second copy also declares an authority class this mission does not admit, which is the probe:
        without that gate, a workstream whose identity is not even settled would collect a second reason.
        """
        streams = submissions_body()["workstreams"]
        streams[1] = dict(streams[1], id=streams[0]["id"], dependencies=[], authority_class="authorized-fan-in")
        result = self.compile_result(submissions=submissions_body(workstreams=streams))
        self.named(result, "more than once")
        self.assertEqual(len(result["reasons"]), 1, result["reasons"])

    def test_the_same_unadmitted_authority_class_does_produce_a_reason_on_its_own(self) -> None:
        # The positive control for the probe above: `authorized-fan-in` is refused when the id is unique,
        # so the single-reason assertion is about the repeated id having stopped that check.
        streams = submissions_body()["workstreams"]
        streams[1] = dict(streams[1], authority_class="authorized-fan-in")
        self.named(self.compile_result(submissions=submissions_body(workstreams=streams)), "does not admit")

    def test_a_five_thousand_workstream_chain_compiles(self) -> None:
        """The iterative walk, proved on an input a recursive one would kill.

        5000 exceeds CPython's default recursion limit by an order of magnitude, so a depth-first
        recursive acyclicity walk over this chain would raise `RecursionError` instead of compiling. The
        node ceiling is raised for this one compilation, because a bounded wave is the default and this
        input is about the ALGORITHM rather than about a plausible wave.
        """
        profile = self.store("limits", {"schema": LIMITS_SCHEMA, "max_concurrent_nodes": 1,
                                        "max_total_nodes": 5000, "recursive_spawn_generations": 0})
        result = self.compile_result(
            submissions=chain_submissions(5000), extra=("--limits", str(profile))
        )
        plan = self.assert_compiled(result)
        self.assertEqual(len(plan["nodes"]), 5000)
        self.assertEqual(len(plan["edges"]), 4999)

    def test_a_five_thousand_workstream_cycle_is_refused_rather_than_crashing(self) -> None:
        profile = self.store("limits", {"schema": LIMITS_SCHEMA, "max_concurrent_nodes": 1,
                                        "max_total_nodes": 5000, "recursive_spawn_generations": 0})
        done = self.run_tool(
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", str(self.store("submissions", seal(chain_submissions(5000, close_the_loop=True)))),
            "--at", AT,
            "--limits", str(profile),
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr[-400:])
        self.assertNotIn(b"RecursionError", done.stderr)
        result = json.loads(done.stdout.decode("utf-8"))
        self.named(result, "cyclic")
        self.assertIsNone(result["plan"])


class CustodyExclusivityTests(AdmissionCase):
    """One owner per worktree, and no two workstreams claiming overlapping files."""

    def two(self, first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
        return self.compile_result(submissions=submissions_body(workstreams=[first, second]))

    def test_two_workstreams_claiming_one_worktree_are_refused(self) -> None:
        result = self.two(
            workstream("ws-alpha", worktree=".worktrees/shared", files=("a.py",)),
            workstream("ws-beta", worktree=".worktrees/shared", files=("b.py",)),
        )
        self.named(result, "both claim worktree custody", "custody is exclusive")

    def test_two_workstreams_claiming_one_file_are_refused(self) -> None:
        result = self.two(
            workstream("ws-alpha", files=("src/app.py",)),
            workstream("ws-beta", files=("src/app.py",)),
        )
        self.named(result, "both claim file custody", "src/app.py")

    def test_a_file_inside_another_workstreams_directory_is_refused(self) -> None:
        result = self.two(
            workstream("ws-alpha", files=("src",)),
            workstream("ws-beta", files=("src/app.py",)),
        )
        self.named(result, "which is inside 'src'", "two depths")

    def test_a_worktree_nested_in_another_worktree_is_refused(self) -> None:
        result = self.two(
            workstream("ws-alpha", worktree=".worktrees/outer"),
            workstream("ws-beta", worktree=".worktrees/outer/inner"),
        )
        self.named(result, "inside '.worktrees/outer'")

    def test_paths_that_merely_share_a_string_prefix_are_admitted(self) -> None:
        """The positive control for containment: `src/app.py` is a STRING prefix of `src/app.py.bak`
        and contains nothing, so comparing custody by `startswith` would refuse a legal wave."""
        plan = self.assert_compiled(
            self.two(
                workstream("ws-alpha", files=("src/app.py",)),
                workstream("ws-beta", files=("src/app.py.bak",)),
            )
        )
        self.assertEqual([node["file_custody"] for node in plan["nodes"]], [["src/app.py"], ["src/app.py.bak"]])

    def test_one_workstream_may_own_a_directory_and_a_file_inside_it(self) -> None:
        # The other positive control: containment is refused BETWEEN workstreams, and a single owner
        # claiming both a directory and something under it has not collided with anyone.
        plan = self.assert_compiled(
            self.two(
                workstream("ws-alpha", files=("src", "src/app.py")),
                workstream("ws-beta", files=("tests/test_app.py",)),
            )
        )
        self.assertEqual(plan["nodes"][0]["file_custody"], ["src", "src/app.py"])


class CapabilityFeasibilityTests(AdmissionCase):
    """Demands are closed, and every demand a snapshot can speak to must be an OBSERVED capability."""

    def with_uv(self, value: str | None) -> Path:
        return self.resealed(
            f"snapshot-uv-{value}", FIXTURES["snapshot"], lambda doc: doc["host_capabilities"].update(uv=value)
        )

    def uv_submissions(self) -> dict[str, Any]:
        streams = [workstream("ws-gate", demands=("repository-gate-execution", "uv-python-toolchain"))]
        return submissions_body(workstreams=streams, declared_concurrency=1)

    def test_an_unobserved_capability_is_infeasible(self) -> None:
        self.assert_compiled(  # positive control: the same demand against an OBSERVED uv compiles
            self.compile_result(snapshot=self.with_uv("0.9.9"), submissions=self.uv_submissions())
        )
        result = self.compile_result(snapshot=self.with_uv(None), submissions=self.uv_submissions())
        self.named(result, "observed no host_capabilities.uv", "cannot be planned onto a capability")

    def test_a_capability_the_snapshot_names_among_its_unknowns_is_infeasible(self) -> None:
        self.assert_compiled(self.compile_result())  # positive control

        def name_it_unknown(document: dict[str, Any]) -> None:
            document["unknowns"] = sorted(
                document["unknowns"] + [{"dimension": "host_capabilities.git", "reason": "not observed"}],
                key=lambda entry: entry["dimension"],
            )

        snapshot = self.resealed("git-unknown", FIXTURES["snapshot"], name_it_unknown)
        self.named(
            self.compile_result(snapshot=snapshot),
            "names host_capabilities.git among its own unknowns",
            "an unobserved capability is not an available one",
        )

    def test_a_demand_no_snapshot_field_reports_is_admitted_as_declared(self) -> None:
        """`subagent-dispatch` is in the closed set and maps onto no observation, so it cannot be found
        infeasible here. The residuals say so; this test is what makes that statement checkable."""
        streams = [workstream("ws-dispatch", demands=("advisory-artifact-write", "subagent-dispatch"))]
        plan = self.assert_compiled(
            self.compile_result(submissions=submissions_body(workstreams=streams, declared_concurrency=1))
        )
        self.assertEqual(plan["nodes"][0]["capability_demands"], ["advisory-artifact-write", "subagent-dispatch"])

    def test_a_demand_outside_the_closed_set_is_refused_exactly_once(self) -> None:
        streams = [workstream("ws-magic", demands=("telekinesis",))]
        result = self.compile_result(submissions=submissions_body(workstreams=streams, declared_concurrency=1))
        self.named(result, "telekinesis", "an open vocabulary")
        self.assertEqual(len(result["reasons"]), 1, "one mistake must not produce two reasons")


class ResourceBoundsTests(AdmissionCase):
    """The two closed bounds, each tested AT the limit, one under it, and one over it."""

    def profile(self, total: int, concurrent: int) -> Path:
        return self.store(
            f"limits-{total}-{concurrent}",
            {
                "schema": LIMITS_SCHEMA,
                "max_concurrent_nodes": concurrent,
                "max_total_nodes": total,
                "recursive_spawn_generations": 0,
            },
        )

    def compile_with(self, total: int, concurrent: int, declared: int) -> dict[str, Any]:
        return self.compile_result(
            submissions=submissions_body(declared_concurrency=declared),
            extra=("--limits", str(self.profile(total, concurrent))),
        )

    def test_two_workstreams_at_a_ceiling_of_two_compile(self) -> None:
        self.assert_compiled(self.compile_with(2, 2, 2))

    def test_two_workstreams_one_under_a_ceiling_of_three_compile(self) -> None:
        self.assert_compiled(self.compile_with(3, 2, 2))

    def test_two_workstreams_one_over_a_ceiling_of_one_are_refused(self) -> None:
        self.named(self.compile_with(1, 1, 1), "propose 2 workstreams against the admitted ceiling of 1")

    def test_concurrency_at_the_ceiling_compiles_and_is_recorded(self) -> None:
        plan = self.assert_compiled(self.compile_with(4, 2, 2))
        self.assertEqual(plan["declared_concurrency"], 2)
        self.assertEqual(plan["limits"]["max_concurrent_nodes"], 2)

    def test_concurrency_one_under_the_ceiling_compiles(self) -> None:
        self.assert_compiled(self.compile_with(4, 2, 1))

    def test_concurrency_one_over_the_ceiling_is_refused(self) -> None:
        self.named(self.compile_with(4, 2, 3), "declare 3 concurrent workstreams", "cannot widen its own")

    def test_a_declared_concurrency_of_zero_is_refused_as_a_shape(self) -> None:
        # The bound is about being too wide; zero is not a narrower wave, it is an unrunnable one.
        self.named(self.compile_with(4, 2, 0), "declared_concurrency is not an integer of at least 1")


class SynthesisTests(AdmissionCase):
    """What the plan and its diff are DERIVED to be, as opposed to what a submission asked for."""

    def test_node_ids_are_the_submitted_workstream_ids_and_the_nodes_are_ordered(self) -> None:
        plan = self.assert_compiled(self.compile_result())
        self.assertEqual([node["node_id"] for node in plan["nodes"]], ["ws-cartography", "ws-compiler"])
        self.assertEqual(plan["edges"], [{"from": "ws-cartography", "to": "ws-compiler"}])
        self.assertEqual(plan["revision"], 1)
        self.assertIsNone(plan["supersedes"], "a first revision follows nothing")

    def test_no_node_carries_a_model_or_an_effort(self) -> None:
        """The pre-spawn contract is the only place a runtime route is admitted, so the closed node key
        set is the enforcement: a planning preference cannot masquerade as a RuntimeAssignment."""
        plan = self.assert_compiled(self.compile_result())
        for node in plan["nodes"]:
            self.assertEqual(
                sorted(node),
                [
                    "authority_class", "capability_demands", "dependencies", "file_custody", "node_id",
                    "objective", "output_schema", "worktree_custody", "wrong_output_class",
                ],
            )

    def test_the_output_schema_is_derived_from_the_authority_class(self) -> None:
        streams = [
            workstream("ws-advisory"),
            workstream("ws-writer", authority_class="owned-worktree-write", worktree=".worktrees/w"),
        ]
        plan = self.assert_compiled(self.compile_result(submissions=submissions_body(workstreams=streams)))
        self.assertEqual(
            [node["output_schema"] for node in plan["nodes"]],
            ["agentic-sdlc/advisory-submission@1", "agentic-sdlc/worktree-submission@1"],
        )

    def test_the_wrong_output_class_is_derived_from_authority_and_position(self) -> None:
        """An advisory node with a dependent DERAILS what reads it; one with none is only a RETRY.

        Submitted values cannot influence this: `workstream()` never sends a wrong-output class, and the
        node key set has no field for one, so a submitter cannot grade its own blast radius.
        """
        streams = [
            workstream("ws-read", files=("a.py",)),
            workstream("ws-uses-it", dependencies=("ws-read",), files=("b.py",)),
            workstream("ws-write", authority_class="owned-worktree-write", worktree=".worktrees/w"),
        ]
        plan = self.assert_compiled(self.compile_result(submissions=submissions_body(workstreams=streams)))
        derived = {node["node_id"]: node["wrong_output_class"] for node in plan["nodes"]}
        self.assertEqual(derived, {"ws-read": "derail", "ws-uses-it": "retry", "ws-write": "degrade"})

    def test_a_first_waves_diff_adds_its_whole_graph_and_removes_nothing(self) -> None:
        result = self.compile_result()
        plan = self.assert_compiled(result)
        diff = result["diff"]
        self.assertIsNone(diff["prior_plan_digest"], "a first wave follows no plan")
        self.assertEqual(diff["plan_digest"], plan["digest"])
        self.assertEqual(diff["digest"], expected_digest(diff))
        by_kind: dict[str, list[str]] = {}
        for change in diff["changes"]:
            by_kind.setdefault(change["kind"], []).append(change["subject"])
            self.assertTrue(change["semantic"], f"{change['kind']} of {change['subject']} alters meaning")
        self.assertEqual(by_kind["added-node"], ["ws-cartography", "ws-compiler"])
        self.assertEqual(by_kind["authority"], ["ws-cartography", "ws-compiler"])
        self.assertEqual(by_kind["added-edge"], ["ws-cartography -> ws-compiler"])
        self.assertEqual(
            by_kind["custody-boundary"],
            [
                ".worktrees/wave-plan-compiler",
                "skills/agentic-sdlc/tools/wave-plan-compiler.py",
                "tests/test_wave_plan_compiler.py",
            ],
        )
        self.assertEqual(set(by_kind) & {"removed-node", "removed-edge", "changed-node"}, set())

    def test_a_prose_only_change_is_recorded_as_not_semantic(self) -> None:
        """Issue 16 keeps a prose change separate from one that alters meaning, and a reordering cannot
        arise at all: every list in a plan has exactly one canonical order."""
        first = self.compile_result(extra=("--out", str(self.work / "prior.json")))
        self.assert_compiled(first)
        streams = submissions_body()["workstreams"]
        streams[1]["objective"] = "the same work, described in different words"
        result = self.compile_result(
            submissions=submissions_body(workstreams=streams),
            extra=("--prior-plan", str(self.work / "prior.json")),
        )
        self.assert_compiled(result)
        changed = [change for change in result["diff"]["changes"] if change["kind"] == "changed-node"]
        self.assertEqual([change["subject"] for change in changed], ["ws-compiler"])
        self.assertFalse(changed[0]["semantic"], "an objective is prose")
        self.assertEqual([change["kind"] for change in result["diff"]["changes"]], ["changed-node"])

    def test_a_semantic_change_beside_the_prose_is_recorded_as_semantic(self) -> None:
        # The positive control for the test above: the same shape of change with a real field moving.
        self.assert_compiled(self.compile_result(extra=("--out", str(self.work / "prior.json"))))
        streams = submissions_body()["workstreams"]
        streams[1]["capability_demands"] = ["git-worktree-write", "python-execution", "repository-read"]
        result = self.compile_result(
            submissions=submissions_body(workstreams=streams),
            extra=("--prior-plan", str(self.work / "prior.json")),
        )
        self.assert_compiled(result)
        changed = [change for change in result["diff"]["changes"] if change["kind"] == "changed-node"]
        self.assertTrue(changed[0]["semantic"])

    def test_recompiling_the_same_submissions_against_their_own_plan_is_refused(self) -> None:
        prior = self.work / "prior.json"
        self.assert_compiled(self.compile_result(extra=("--out", str(prior))))
        result = self.compile_result(extra=("--prior-plan", str(prior)))
        self.named(result, "no delta to name", "a revision that changes nothing is not a revision")
        self.assertIsNone(result["plan"], "a refusal seals nothing")

    def test_a_moved_custody_boundary_names_both_owners(self) -> None:
        prior = self.work / "prior.json"
        self.assert_compiled(self.compile_result(extra=("--out", str(prior))))
        streams = submissions_body()["workstreams"]
        streams[0]["file_custody"] = ["tests/test_wave_plan_compiler.py"]
        streams[1]["file_custody"] = ["skills/agentic-sdlc/tools/wave-plan-compiler.py"]
        result = self.compile_result(
            submissions=submissions_body(workstreams=streams),
            extra=("--prior-plan", str(prior)),
        )
        self.assert_compiled(result)
        moved = [
            change
            for change in result["diff"]["changes"]
            if change["kind"] == "custody-boundary" and change["subject"] == "tests/test_wave_plan_compiler.py"
        ]
        self.assertEqual(len(moved), 1)
        self.assertIn("moves from node 'ws-compiler' to node 'ws-cartography'", moved[0]["evidence"])


class PartialWriteTests(AdmissionCase):
    """The one partial effect two exclusive writes can produce, and the code reserved for it."""

    def setUp(self) -> None:
        super().setUp()
        if os.geteuid() == 0:
            self.skipTest("a mode-0o500 directory does not stop root, so this refusal cannot be provoked")

    def test_a_plan_written_beside_an_unwritable_diff_exits_four_and_says_so(self) -> None:
        out = self.work / "plan.json"
        locked = self.work / "locked"
        locked.mkdir()
        self.addCleanup(locked.chmod, 0o700)
        locked.chmod(0o500)
        done = self.run_tool(
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", str(self.store("submissions", seal(submissions_body()))),
            "--at", AT,
            "--out", str(out),
            "--diff-out", str(locked / "diff.json"),
        )
        self.assertEqual(done.returncode, 4, done.stderr)
        self.assertIn(b"the pair on disk is incomplete", done.stderr)
        result = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(result["verdict"], COMPILED, "the documents were derived; only delivery failed")
        self.assertEqual(result["exit_code"], 4)
        self.assertEqual(result["out"], str(out))
        self.assertIsNone(result["diff_out"], "a document that did not land is never reported as written")
        self.assertTrue(out.exists())

    def test_the_same_two_destinations_writable_exit_zero(self) -> None:
        # The positive control: mode 0o500 is the whole difference between exit 4 and exit 0.
        writable = self.work / "writable"
        writable.mkdir()
        result = self.compile_result(
            extra=("--out", str(self.work / "plan.json"), "--diff-out", str(writable / "diff.json"))
        )
        self.assert_compiled(result)
        self.assertEqual(result["exit_code"], EXIT_OK)
        self.assertEqual(result["diff_out"], str(writable / "diff.json"))


class WriteDocumentRaceGuardTests(unittest.TestCase):
    """`write_document`'s own `O_EXCL`, isolated from `check_output_path`'s earlier existence check.

    `compile`'s CLI path always refuses an occupied `--out`/`--diff-out` before `write_document` is
    ever reached, so a subprocess-level test can never exercise `O_EXCL` losing a race to a file that
    appeared in between: it would only ever prove the earlier check. This class imports the tool
    directly -- its hyphenated filename means a plain `import` statement cannot name it, so
    `importlib.util.spec_from_file_location` loads it under a module name of this test's choosing --
    and calls `write_document` against a target that already exists, which is exactly what a racer
    winning that gap would leave behind.
    """

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("wave_plan_compiler_race_guard", TOOL)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name).resolve()

    def test_a_pre_existing_target_is_left_untouched_and_reports_nothing_created(self) -> None:
        target = self.work / "plan.json"
        target.write_bytes(b"a racer's file, already here\n")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            state = self.module.write_document(target, {"schema": "agentic-sdlc/wave-plan@1"}, "--out")
        self.assertEqual(state, self.module.WRITE_NOTHING)
        self.assertEqual(target.read_bytes(), b"a racer's file, already here\n")
        self.assertIn("cannot create the --out path", captured.getvalue())
        self.assertIn("nothing was written", captured.getvalue())


class EmptyDiffShapeTests(CompilerCase):
    """The `changes`/`no_delta_reason` cross-check, in both directions, read by `verify --diff`.

    An empty `changes` array on its own cannot tell "these two revisions are identical" from "this diff
    was never computed", and a consumer that bound the digest has no follow-up question to ask. So the
    schema requires the emptiness to be stated, and a populated diff may not also claim it.
    """

    def empty(self, **overrides: Any) -> dict[str, Any]:
        body = diff_body(changes=[], no_delta_reason=NO_DELTA, prior_plan_digest=fake_digest("prior"))
        body.update(overrides)
        return seal(body)

    def test_an_empty_diff_that_names_its_prior_plan_and_says_why_verifies(self) -> None:
        # THE positive control for the three refusals below: this exact document is admitted.
        result = self.verify_diff(self.empty())
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])
        self.assertEqual(result["diff"]["changes"], [])

    def test_an_empty_diff_that_does_not_say_it_is_empty_on_purpose_is_refused(self) -> None:
        self.named(self.verify_diff(self.empty(no_delta_reason=None)), "must SAY it is empty on purpose")

    def test_an_empty_diff_whose_reason_is_an_empty_string_is_refused(self) -> None:
        self.named(self.verify_diff(self.empty(no_delta_reason="")), "must SAY it is empty on purpose")

    def test_a_diff_that_names_changes_and_also_claims_no_delta_is_refused(self) -> None:
        self.named(
            self.verify_diff(seal(diff_body(no_delta_reason=NO_DELTA))),
            "claims both a delta and no delta",
        )

    def test_changes_that_is_not_an_array_at_all_is_refused(self) -> None:
        self.named(self.verify_diff(seal(diff_body(changes={"kind": "added-node"}))), "not a JSON array")


def revision_two(**overrides: Any) -> dict[str, Any]:
    """A second revision of `plan_body()`'s plan: same mission, next number, naming what it supersedes.

    A DISTINCT document from the first revision even when its graph is identical, which is what makes
    the empty-diff case reachable: `diff` refuses one document supplied as both of its revisions.
    """
    body = plan_body(revision=2, supersedes=expected_digest(plan_body()))
    body.update(overrides)
    return seal(body)


class StandaloneDiffTests(CompilerCase):
    """`diff` over two SEALED revisions: what changed, by name, and what an empty answer looks like.

    No sibling fixture is needed here -- both plans are hand-sealed by this module and bind the same
    (fake) mission digest -- so this class runs on a host with no git.
    """

    def diff_result(self, plan: dict[str, Any], prior: dict[str, Any], *, at: str = AT) -> dict[str, Any]:
        return self.result(
            "diff",
            "--plan", str(self.store("newer", plan)),
            "--prior-plan", str(self.store("older", prior)),
            "--at", at,
        )

    def assert_diffed(self, result: dict[str, Any]) -> dict[str, Any]:
        """THE positive control every refusal in this class starts from: this pair yields a diff."""
        self.assertEqual(result["verdict"], COMPILED, result["reasons"])
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["inputs_admitted"])
        self.assertIsNone(result["plan"], "`diff` seals a diff, not a plan")
        self.assertIsNotNone(result["diff"])
        self.assertEqual(result["diff"]["digest"], expected_digest(result["diff"]))
        self.assertEqual(result["diff_digest"], result["diff"]["digest"])
        return result["diff"]

    def rebuilt(self) -> dict[str, Any]:
        """Revision 2 with one node added, one removed, and one changed -- all three at once."""
        nodes = plan_body()["nodes"]
        # The dependency goes with the removed node: a node that still named it would make the plan's
        # own edges disagree with its dependencies, which is a malformed plan rather than a delta.
        kept = dict(
            nodes[1], objective="build the compiler, its diff, and its determinism tests", dependencies=[]
        )
        added = {
            "node_id": "n-docs",
            "objective": "record what the compiler does not check",
            "authority_class": "read-only-advisory",
            "capability_demands": ["repository-read"],
            "dependencies": [],
            "file_custody": ["docs/plans/wave-plan-compiler.md"],
            "worktree_custody": None,
            "output_schema": "agentic-sdlc/advisory-submission@1",
            "wrong_output_class": "retry",
        }
        return revision_two(nodes=sorted([kept, added], key=lambda node: node["node_id"]), edges=[])

    def test_the_added_removed_and_changed_nodes_are_each_named(self) -> None:
        diff = self.assert_diffed(self.diff_result(self.rebuilt(), seal(plan_body())))
        by_kind: dict[str, list[str]] = {}
        for change in diff["changes"]:
            by_kind.setdefault(change["kind"], []).append(change["subject"])
        self.assertEqual(by_kind["added-node"], ["n-docs"])
        self.assertEqual(by_kind["removed-node"], ["n-cartography"])
        self.assertEqual(by_kind["changed-node"], ["n-compiler"])
        self.assertEqual(by_kind["removed-edge"], ["n-cartography -> n-compiler"])
        self.assertIsNone(diff["no_delta_reason"], "a diff that names changes claims no emptiness")
        self.assertEqual(diff["prior_plan_digest"], expected_digest(plan_body()))
        self.assertEqual(diff["plan_digest"], self.rebuilt()["digest"])

    def test_a_changed_node_names_the_fields_that_differ(self) -> None:
        diff = self.assert_diffed(self.diff_result(self.rebuilt(), seal(plan_body())))
        changed = [change for change in diff["changes"] if change["kind"] == "changed-node"]
        for field in ("'dependencies'", "'objective'"):
            self.assertIn(field, changed[0]["evidence"], "every differing field is named")
        self.assertTrue(changed[0]["semantic"], "a dependency moved beside the prose, so meaning changed")

    def test_two_identical_revisions_yield_an_explicitly_empty_diff(self) -> None:
        diff = self.assert_diffed(self.diff_result(revision_two(), seal(plan_body())))
        self.assertEqual(diff["changes"], [], "identical graphs have no delta to name")
        self.assertIsInstance(diff["no_delta_reason"], str)
        for fragment in ("the two revisions are identical", "empty on purpose"):
            self.assertIn(fragment, diff["no_delta_reason"])
        # And the emptiness survives the tool's OWN verify, so it is a bindable document rather than a
        # shape only the compiler will accept.
        self.assertEqual(self.verify_diff(diff, name="empty")["verdict"], VERIFIED)

    def test_the_empty_diff_still_names_both_revisions_it_compared(self) -> None:
        diff = self.assert_diffed(self.diff_result(revision_two(), seal(plan_body())))
        self.assertEqual(diff["prior_plan_digest"], expected_digest(plan_body()))
        self.assertEqual(diff["plan_digest"], revision_two()["digest"])
        self.assertNotEqual(diff["plan_digest"], diff["prior_plan_digest"])

    def test_one_document_supplied_as_both_revisions_is_refused(self) -> None:
        sealed = seal(plan_body())
        path = str(self.store("both", sealed))
        result = self.result("diff", "--plan", path, "--prior-plan", path, "--at", AT)
        self.named(result, "one document is not two revisions", "superseding itself")
        self.assertIsNone(result["diff"], "a refusal seals nothing")

    def test_two_plans_bound_to_different_missions_cannot_be_diffed(self) -> None:
        self.assert_diffed(self.diff_result(revision_two(), seal(plan_body())))  # positive control
        elsewhere = dict(plan_body()["inputs"], mission_digest=fake_digest("another mission"))
        result = self.diff_result(revision_two(), seal(plan_body(inputs=elsewhere)))
        self.named(result, "a diff across two missions is not a delta", "binds mission contract digest")

    def test_two_plans_naming_different_mission_ids_cannot_be_diffed(self) -> None:
        result = self.diff_result(revision_two(mission_id="mission-something-else"), seal(plan_body()))
        self.named(result, "the two plans name mission_id")

    def test_a_malformed_newer_plan_is_reported_against_the_plan_position(self) -> None:
        result = self.diff_result(revision_two(edges=[]), seal(plan_body()))
        self.named(result, "two different graphs")
        self.assertIn("plan", {check["slug"] for check in result["checks"] if not check["met"]})
        self.assertNotIn("prior-plan", {check["slug"] for check in result["checks"] if not check["met"]})

    def test_a_malformed_older_plan_is_reported_against_the_prior_plan_position(self) -> None:
        # The positive control for the assertion above: the same mutation in the other position moves
        # the reported group, so the two are really told apart rather than both named "the wave plan".
        result = self.diff_result(revision_two(), seal(plan_body(edges=[])))
        self.named(result, "two different graphs")
        self.assertIn("prior-plan", {check["slug"] for check in result["checks"] if not check["met"]})
        self.assertNotIn("plan", {check["slug"] for check in result["checks"] if not check["met"]})

    def test_a_diff_supplied_as_a_plan_is_refused_by_schema(self) -> None:
        self.named(self.diff_result(seal(diff_body()), seal(plan_body())), "the wave plan declares schema")

    def test_a_plan_whose_content_does_not_derive_its_digest_is_refused(self) -> None:
        tampered = dict(seal(plan_body()), revision=7)
        self.named(self.diff_result(tampered, seal(plan_body())), "does not re-derive")

    def test_the_diff_command_writes_no_file(self) -> None:
        before = sorted(path.name for path in self.work.iterdir())
        self.assert_diffed(self.diff_result(self.rebuilt(), seal(plan_body())))
        after = sorted(path.name for path in self.work.iterdir())
        self.assertEqual(after, sorted(set(before) | {"newer.json", "older.json"}))

    def test_an_unusable_plan_file_is_exit_two_rather_than_a_refusal(self) -> None:
        done = self.run_tool(
            "diff",
            "--plan", str(self.work / "absent.json"),
            "--prior-plan", str(self.store("older", seal(plan_body()))),
            "--at", AT,
        )
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"", "an unusable input publishes no result document")

    def test_a_malformed_instant_is_refused_before_either_plan_is_read(self) -> None:
        done = self.run_tool(
            "diff", "--plan", str(self.work / "absent.json"), "--prior-plan", str(self.work / "gone.json"),
            "--at", "2026-8-19T04:00:00Z",
        )
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"is not a YYYY-MM-DDTHH:MM:SSZ instant", done.stderr)


def reordered(value: Any) -> Any:
    """The same document with every object's keys in REVERSED insertion order, lists left alone.

    Reversing rather than shuffling, so the test is deterministic itself. List order is preserved
    because it is meaningful input -- the tool requires ascending ids and rejects the rest -- while key
    order is not, and a digest that depended on it would not be a digest of the document's meaning.
    """
    if isinstance(value, dict):
        return {key: reordered(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reordered(entry) for entry in value]
    return value


class DeterminismTests(AdmissionCase):
    """Identical inputs seal identical BYTES, and neither the environment nor key order can move them.

    The hash-seed case is the one that needs a positive control of its own: comparing two runs is only
    evidence if the two runs really had different string hashing, so
    `test_the_two_hash_seeds_really_do_change_this_interpreters_string_hashing` proves the mechanism is
    live in this interpreter before the comparison below is allowed to mean anything.
    """

    def sealed_pair(self, result: dict[str, Any]) -> bytes:
        """The two sealed documents as bytes. Deliberately NOT the whole result document: that also
        carries the absolute output paths of the run, which depend on the process directory."""
        self.assert_compiled(result)
        return canonical(result["plan"]) + canonical(result["diff"])

    def test_two_compilations_of_one_input_set_are_byte_identical(self) -> None:
        submissions = str(self.store("submissions", seal(submissions_body())))
        argv = (
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", submissions,
            "--at", AT,
        )
        first, second = self.run_tool(*argv), self.run_tool(*argv)
        self.assertEqual(first.returncode, EXIT_OK, first.stderr)
        self.assertEqual(
            first.stdout, second.stdout, "two runs over one input set produced two different results"
        )
        self.assertEqual(json.loads(first.stdout)["verdict"], COMPILED)

    def test_the_two_hash_seeds_really_do_change_this_interpreters_string_hashing(self) -> None:
        # The positive control for the test below. If hash randomization were disabled in this
        # interpreter, a set-iteration order that DID reach the sealed bytes would still compare equal.
        program = "print(hash('agentic-sdlc/wave-plan@1'))"
        hashes = {
            _run([sys.executable, "-c", program], cwd=self.work, extra={"PYTHONHASHSEED": seed}).stdout
            for seed in ("1", "4242")
        }
        self.assertEqual(len(hashes), 2, "hash randomization is off, so the seed comparison proves nothing")

    def test_a_different_hash_seed_seals_the_same_bytes(self) -> None:
        submissions = str(self.store("submissions", seal(submissions_body())))
        argv = (
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", submissions,
            "--at", AT,
        )
        first = self.result(*argv, extra={"PYTHONHASHSEED": "1"})
        second = self.result(*argv, extra={"PYTHONHASHSEED": "4242"})
        self.assertEqual(
            self.sealed_pair(first),
            self.sealed_pair(second),
            "a set or dict iteration order reached the sealed documents",
        )

    def test_reordered_submission_keys_seal_the_same_documents(self) -> None:
        sealed = seal(submissions_body())
        straight = self.compile_result(submissions=self.store("straight", sealed))
        shuffled = self.compile_result(submissions=self.store("shuffled", reordered(sealed)))
        self.assertEqual(self.sealed_pair(straight), self.sealed_pair(shuffled))
        # And the input's own digest survived the reordering, which is what makes the two admissible at
        # all: the digest is over the canonical form, not over the bytes on disk.
        self.assertEqual(straight["inputs"], shuffled["inputs"])

    def test_the_process_directory_does_not_reach_the_sealed_documents(self) -> None:
        submissions = self.store("submissions", seal(submissions_body()))
        elsewhere = self.work / "elsewhere"
        elsewhere.mkdir()
        here = self.compile_result(submissions=submissions)
        there = self.result(
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", str(submissions),
            "--at", AT,
            cwd=elsewhere,
        )
        self.assertEqual(self.sealed_pair(here), self.sealed_pair(there))

    def test_a_relative_output_path_is_resolved_against_the_process_directory(self) -> None:
        # The honest other half of the test above: cwd DOES decide where a relative --out lands, and the
        # result document reports that absolute path. It is the one cwd-dependent value, and it is not
        # in either sealed document.
        elsewhere = self.work / "elsewhere"
        elsewhere.mkdir()
        result = self.result(
            "compile",
            "--mission", str(FIXTURES["mission"]),
            "--snapshot", str(FIXTURES["snapshot"]),
            "--submissions", str(self.store("submissions", seal(submissions_body()))),
            "--at", AT,
            "--out", "plan.json",
            cwd=elsewhere,
        )
        self.assert_compiled(result)
        self.assertEqual(result["out"], str(elsewhere / "plan.json"))
        self.assertTrue((elsewhere / "plan.json").exists())

    def test_the_diff_command_re_derives_exactly_the_diff_compile_sealed(self) -> None:
        """The two paths to a PlanDiff must not be able to disagree: one delta has one digest, whether it
        was sealed beside its plan or re-derived from the two sealed revisions afterwards."""
        prior = self.store("prior", self.mission_bound_plan())
        out = self.work / "plan.json"
        compiled = self.compile_result(extra=("--prior-plan", str(prior), "--out", str(out)))
        self.assert_compiled(compiled)
        standalone = self.result("diff", "--plan", str(out), "--prior-plan", str(prior), "--at", AT)
        self.assertEqual(standalone["verdict"], COMPILED, standalone["reasons"])
        self.assertEqual(canonical(standalone["diff"]), canonical(compiled["diff"]))

    def test_the_same_two_revisions_diff_to_the_same_bytes_twice(self) -> None:
        plan = str(self.store("newer", self.mission_bound_plan(revision=2, supersedes=fake_digest("older"))))
        prior = str(self.store("older", self.mission_bound_plan()))
        argv = ("diff", "--plan", plan, "--prior-plan", prior, "--at", AT)
        first, second = self.run_tool(*argv), self.run_tool(*argv)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["verdict"], COMPILED, json.loads(first.stdout)["reasons"])


#: The `os` attributes that read ambient state rather than an explicit argument. `os.devnull`,
#: `os.open`, and `os.path.*` are deliberately absent: a constant, an explicit path write, and path
#: resolution are not ambient inputs.
AMBIENT_OS_ATTRIBUTES = ("clock_gettime", "environ", "environb", "getenv", "putenv", "times", "urandom")


class AmbientInputDisciplineTests(unittest.TestCase):
    """The two ambient inputs a deterministic tool must not have: an environment read and a clock.

    Read with `ast` over both files rather than by substring, because the tool's own docstring contains
    the words `os.environ` in the sentence that PROMISES it does not appear -- a grep would fail on the
    promise itself, which is the failure mode that makes a prose claim worthless.
    """

    def ambient(self, source: str) -> list[ast.Attribute]:
        return [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in AMBIENT_OS_ATTRIBUTES
        ]

    def os_attributes(self, source: str) -> set[str]:
        return {
            node.attr
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os"
        }

    def test_the_extractor_sees_the_os_calls_the_tool_really_makes(self) -> None:
        # The positive control for the two assertions below: this extractor DOES find `os` attributes in
        # this file, so finding no ambient one is evidence rather than a broken walk.
        found = self.os_attributes(TOOL.read_text(encoding="utf-8"))
        self.assertLessEqual({"open", "fsync", "fdopen"}, found)

    def test_the_extractor_sees_an_ambient_read_when_there_is_one(self) -> None:
        # The positive control for the classifier itself, on a source that does read the environment.
        self.assertEqual(len(self.ambient("import os\nvalue = os.environ['PATH']\n")), 1)

    def test_the_tool_reads_no_environment_variable_and_no_clock(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertEqual(
            [node.attr for node in self.ambient(source)],
            [],
            "an ambient read would make two runs over one input set separable",
        )
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                names = sorted(alias.name for alias in node.names)
                self.assertEqual(names, [], f"`from os import {names}` bypasses the check above")

    def test_this_test_module_touches_the_environment_only_in_its_constructed_env_helper(self) -> None:
        """Every spawn here builds its environment from an allowlist, and this is what keeps it true.

        A test that reached for `os.environ` directly would hand a tool whatever the developer's shell
        happened to hold, which is how a host-dependent pass hides a clean-machine failure.
        """
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "constructed_environment"
        ]
        self.assertEqual(len(helper), 1)
        first, last = helper[0].lineno, helper[0].end_lineno or helper[0].lineno
        touched = [node.lineno for node in self.ambient(source)]
        self.assertTrue(touched, "no environment access found at all, so this assertion proves nothing")
        for line in sorted(touched):
            self.assertTrue(
                first <= line <= last,
                f"line {line} reads the ambient environment outside constructed_environment()",
            )


class ChangeKindCoverageTests(CompilerCase):
    """Which of the sixteen change kinds a wave-plan@1 can actually produce, and what says so.

    The tool declares the other nine unreachable in its residuals. A declared limit nobody checks is
    how a residual and the code drift apart, so this class asserts BOTH halves: every reachable kind is
    observed in a real diff, and every unreachable one is named in the residual that admits it.
    """

    def diff_of(self, plan: dict[str, Any], prior: dict[str, Any], name: str) -> dict[str, Any]:
        result = self.result(
            "diff",
            "--plan", str(self.store(f"{name}-newer", plan)),
            "--prior-plan", str(self.store(f"{name}-older", prior)),
            "--at", AT,
        )
        self.assertEqual(result["verdict"], COMPILED, result["reasons"])
        return result

    def unlinked(self) -> dict[str, Any]:
        """`plan_body()`'s two nodes with the dependency and its edge removed, so revision 2 ADDS one."""
        nodes = plan_body()["nodes"]
        detached = dict(nodes[1], dependencies=[], wrong_output_class="degrade")
        return seal(plan_body(nodes=[dict(nodes[0], wrong_output_class="retry"), detached], edges=[]))

    def test_every_reachable_change_kind_is_observed_and_the_rest_are_declared_unreachable(self) -> None:
        nodes = plan_body()["nodes"]
        added = {
            "node_id": "n-docs",
            "objective": "record what the compiler does not check",
            "authority_class": "read-only-advisory",
            "capability_demands": ["repository-read"],
            "dependencies": [],
            "file_custody": ["docs/plans/wave-plan-compiler.md"],
            "worktree_custody": None,
            "output_schema": "agentic-sdlc/advisory-submission@1",
            "wrong_output_class": "retry",
        }
        rebuilt = seal(
            plan_body(
                revision=2,
                supersedes=expected_digest(plan_body()),
                nodes=sorted(
                    [dict(nodes[1], dependencies=[], objective="restated"), added],
                    key=lambda node: node["node_id"],
                ),
                edges=[],
            )
        )
        removals = self.diff_of(rebuilt, seal(plan_body()), "removals")
        relinked = seal(plan_body(revision=2, supersedes=self.unlinked()["digest"]))
        additions = self.diff_of(relinked, self.unlinked(), "additions")
        observed = {change["kind"] for change in removals["diff"]["changes"]}
        observed |= {change["kind"] for change in additions["diff"]["changes"]}
        self.assertEqual(observed, set(REACHABLE_KINDS), "the reachable vocabulary moved")
        residuals = " || ".join(removals["residuals"])
        for kind in set(CHANGE_KINDS) - set(REACHABLE_KINDS):
            self.assertIn(kind, residuals, f"{kind} is unreachable and no residual admits it")


def writer(identifier: str, *, worktree: str, files: tuple[str, ...] = ()) -> dict[str, Any]:
    """One owned-worktree-write workstream, which is the only class that can hold a worktree usefully."""
    return workstream(
        identifier,
        authority_class="owned-worktree-write",
        demands=("git-worktree-write",),
        files=files,
        worktree=worktree,
    )


class DeclaredLimitTests(AdmissionCase):
    """The limits the tool DECLARES rather than checks, pinned so the declaration cannot rot silently.

    Each test asserts the limited behaviour AND that a residual names the limit, so closing one of them
    in a later revision fails here and has to update the residual in the same change.
    """

    def residual_names(self, result: dict[str, Any], fragment: str) -> None:
        self.assertIn(fragment, " || ".join(result["residuals"]))

    def test_a_file_claim_inside_another_nodes_worktree_is_admitted_and_the_owner_is_deterministic(self) -> None:
        """Custody is compared WITHIN each kind, so a file claim equal to another node's worktree claim
        is admitted. The plan then draws one boundary for that path, and which node owns it is decided
        by sorted node order rather than by any mapping's insertion order."""
        streams = [
            writer("ws-alpha", worktree=".worktrees/shared"),
            writer("ws-beta", worktree=".worktrees/beta", files=(".worktrees/shared",)),
        ]
        result = self.compile_result(submissions=submissions_body(workstreams=streams))
        self.assert_compiled(result)
        boundaries = [
            change
            for change in result["diff"]["changes"]
            if change["kind"] == "custody-boundary" and change["subject"] == ".worktrees/shared"
        ]
        self.assertEqual(len(boundaries), 1, "one path is one boundary, whichever kind declared it")
        self.assertIn("node 'ws-beta'", boundaries[0]["evidence"], "the later node id owns the path")
        self.residual_names(result, "not detected here")

    def test_the_same_two_claims_within_one_kind_are_refused(self) -> None:
        # The positive control for the admission above: the same collision declared as two file claims,
        # or two worktree claims, is exactly what custody exclusivity refuses.
        streams = [
            writer("ws-alpha", worktree=".worktrees/shared"),
            writer("ws-beta", worktree=".worktrees/shared"),
        ]
        self.named(
            self.compile_result(submissions=submissions_body(workstreams=streams)),
            "both claim worktree custody",
        )

    def test_a_demand_no_snapshot_field_observes_is_admitted_and_the_residual_says_so(self) -> None:
        streams = [workstream("ws-only", demands=("seeds-queue-read", "subagent-dispatch"))]
        result = self.compile_result(submissions=submissions_body(workstreams=streams, declared_concurrency=1))
        plan = self.assert_compiled(result)
        self.assertEqual(plan["nodes"][0]["capability_demands"], ["seeds-queue-read", "subagent-dispatch"])
        self.residual_names(result, "admitted as declared rather than checked")

    def test_the_head_is_carried_and_the_residual_says_nothing_compared_it(self) -> None:
        result = self.compile_result()
        self.assert_compiled(result)
        self.residual_names(result, "head freshness is the admission gate's check")

    def test_a_prior_plan_from_another_mission_ends_the_chain_and_the_residual_says_so(self) -> None:
        prior = self.store("prior", seal(plan_body()))  # bound to fake_digest("mission"), not the real one
        result = self.compile_result(extra=("--prior-plan", str(prior)))
        self.named(result, "a diff across two missions is not a delta", "binds mission contract digest")
        self.assertIn("provenance", {check["slug"] for check in result["checks"] if not check["met"]})
        self.residual_names(result, "revising the contract ENDS a plan chain")

    def test_the_same_prior_plan_bound_to_the_real_mission_compiles(self) -> None:
        # The positive control for the pin: one field of the prior plan is the whole difference.
        prior = self.store("prior", self.mission_bound_plan())
        self.assert_compiled(self.compile_result(extra=("--prior-plan", str(prior))))
