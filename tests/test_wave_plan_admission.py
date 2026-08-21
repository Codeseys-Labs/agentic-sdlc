"""Tests for the plan-admission gate: its schema, its input admission, its six checks, and its IO.

Nine kinds of test live here and they check different things.

The SIBLING FIXTURES are built by RUNNING `mission-contract.py define`, `planning-snapshot.py
capture`, and `wave-plan-compiler.py compile` once per test run, against ONE scratch git repository
that is MUTATED BETWEEN CAPTURES. Nothing here hand-writes a guess of a sibling's sealed form: the
whole point of admitting an input by re-deriving its digest is that a hand-written approximation would
either be rejected for the wrong reason or, worse, accepted while the real sibling's output was not.
That also makes this module the place a divergence surfaces: the tool re-expresses each input's closed
key set rather than importing it, so a sibling that adds a field fails `setUpModule`'s own positive
control instead of being silently refused in production. Capturing a snapshot needs a real `git`, so
every class that consumes one skips with a named reason when git is absent.

SEVEN REAL SNAPSHOTS OF ONE REPOSITORY ARE WHAT MAKE THE CURRENT-STATE CHECKS CHECKABLE. The
freshness anchor is the whole point of this gate, and a resealed hand-mutation of a `head` field
would prove only that the tool compares two strings. So the repository is really moved and really
re-observed: `compiled` (the snapshot the plan is compiled from), `equal` (the same head, captured at
exactly the plan's `compiled_at`), `fresh` (the same head, captured later -- the one input set that
reaches `admitted`), `swapped` (a real `git clone` of the same commit, so the head matches and only
the physical repository differs), `dirty` (one real untracked file), `occupied` (a real `git worktree
add` at the path a plan node claims), `artifact` (a real file under `.sdlc`), and `moved` (a real
second commit). Every refusal below that has a real observation behind it uses one of those.

The INPUT-ADMISSION tests carry a POSITIVE CONTROL: `assert_admitted` asserts the unmutated input set
reaches `inputs_admitted` true with NO reason at all, six met checks, and a sealed report whose
disposition is `admitted`, so a test that stopped exercising its guard would also have to stop
reaching that state. A tolerated subset of reasons would let a guard rot silently; nothing here
tolerates one. Each negative case then asserts the named field appears in a reason AND that nothing
was sealed, because a gate that refuses while still publishing a bindable report is the failure mode
that matters. A CHECK failure is the other shape -- `assert_blocked` -- where the inputs were
admitted, the report IS sealed, and its disposition is `blocked` with the blocker named in its own
check group.

A mutation that tests a SHAPE check is RESEALED and a mutation that tests the DIGEST check is not,
which is not a convenience: `_sealed_input` stops at the first failure in the order schema, keys,
digest, so an unresealed shape mutation would only ever produce the digest reason and the shape guard
would never run. Resealing with this module's own independent derivation is therefore also a
round-trip assertion on every one of those cases.

The REPORT-SHAPE tests hand-seal a `wave-plan-admission@1` with this module's own canonical helpers
and hand it to `verify`, so the tool is proved to agree with the family's published derivation rather
than with itself. One of them seals a report naming ALL ELEVEN of issue 16's check slugs with
disposition `admitted` and an EMPTY deferred list: the slug vocabulary is declared in full precisely
so a later revision's report still verifies against this one's schema, and that promise is only real
if something checks it.

The DEFERRED-DIMENSION tests are the other half of "never vacuously met". They assert the sealed
report enumerates every dimension the tool does not decide, that a dimension outside the closed
vocabulary is refused, and -- the load-bearing one -- that a report reporting a whole dimension as a
MET check while also deferring it is refused as the self-contradiction it is.

The INSTANT tests exist for one character class: the guard is `[0-9]`, not `\\d`, so an Arabic-Indic
digit string that `\\d` would happily accept must be refused -- and the test asserts `\\d` really does
accept it, so the case cannot decay into a tautology. They also prove the guard runs BEFORE any file
is read, which is what makes "this tool reads no clock" checkable rather than aspirational.

The NON-FINITE tests cover both halves of the defence, because they are different code: the three
constant TOKENS reach `parse_constant`, while the literal `1e400` never does -- it is an ordinary
JSON number that overflows during parsing, and the iterative post-parse walk is the only thing that
catches it. Each is placed at a NESTED position, and each carries a finite positive control at the
same position, so the exit 2 is attributable to the non-finiteness rather than to the mutation.

The OUTPUT-DISCIPLINE tests cover the whole `--out` contract: the written bytes are the canonical
sealed report and nothing else, an occupied destination is refused with its content intact, a missing
parent is refused, a destination inside the observed worktree or git dir is refused (including
through a symlinked parent, which is why the tool resolves both sides), an inadmissible input creates
no file at all, and a destination that passes every check but cannot be created is exit 1 with the
report still delivered in the result.

The DETERMINISM tests compare BYTES across two runs and vary the two ambient inputs a sealed document
must not depend on: `PYTHONHASHSEED`, which decides every `set` and `dict` iteration order in the
child, and the process directory. The hash-seed comparison carries its own positive control -- that
the two seeds really do change this interpreter's string hashing -- because comparing two runs of a
tool whose randomization was disabled would prove nothing at all.

The AMBIENT-INPUT tests read both files with `ast` and assert the tool touches no `os` attribute that
reads ambient state, and that THIS module reaches for the environment only inside
`constructed_environment`. A substring search cannot do that job: the tool's docstring contains the
words "environment variable" in the sentence promising it reads none.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import io
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "skills" / "agentic-sdlc" / "tools"
TOOL = TOOLS / "wave-plan-admission.py"
MISSION_TOOL = TOOLS / "mission-contract.py"
SNAPSHOT_TOOL = TOOLS / "planning-snapshot.py"
COMPILER_TOOL = TOOLS / "wave-plan-compiler.py"

ADMISSION_SCHEMA = "agentic-sdlc/wave-plan-admission@1"
RESULT_SCHEMA = "agentic-sdlc/wave-plan-admission-result@1"
PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
MISSION_SCHEMA = "agentic-sdlc/mission-contract@1"
SUBMISSIONS_SCHEMA = "agentic-sdlc/workstream-submissions@1"

ADMITTED = "admitted"
VERIFIED = "verified"
REFUSED = "refused"
BLOCKED = "blocked"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

AT = "2026-08-19T05:00:00Z"
MISSION_ID = "mission-slice-6"

#: The reserved group slug, which no report this revision seals emits, and the eleven issue 16
#: enumerates. Re-expressed here so a vocabulary the tool narrowed would fail rather than agree with
#: itself.
GROUP_SLUG = "admission-checks"
ISSUE_16_SLUGS = (
    "approval-requirements",
    "budgets-and-declared-egress",
    "dependency-and-artifact-availability",
    "fallbacks-and-stop-conditions",
    "gates-and-review-requirements",
    "host-and-tool-capability",
    "policy-and-adr-consistency",
    "route-constraints-and-qualification",
    "snapshot-freshness",
    "target-and-custody-identity",
    "unresolved-prior-effect",
)

#: The six checks this revision decides, in the order the report lists them, and the nine dimensions it
#: does not. Both re-expressed, so a tool that quietly stopped running a check -- or quietly started
#: claiming a deferred one -- fails here instead of agreeing with itself.
RAN_SLUGS = (
    "snapshot-freshness",
    "target-and-custody-identity",
    "dependency-and-artifact-availability",
    "policy-and-adr-consistency",
    "host-and-tool-capability",
    "unresolved-prior-effect",
)
DEFERRED_NAMES = (
    "approval-requirements",
    "budgets-and-declared-egress",
    "dependency-and-artifact-availability:file-custody",
    "dependency-and-artifact-availability:worktree-branch",
    "fallbacks-and-stop-conditions",
    "gates-and-review-requirements",
    "host-and-tool-capability:harness-demands",
    "host-and-tool-capability:version-qualification",
    "policy-and-adr-consistency:adr-applicability",
    "policy-and-adr-consistency:recursive-spawn-generations",
    "route-constraints-and-qualification",
)
#: The five INPUT positions, in result order. `compiled-snapshot` is one of them: the compile-time
#: snapshot is optional, but a supplied one that is inadmissible seals nothing, exactly like the rest.
INPUT_SLUGS = ("wave-plan", "planning-snapshot", "compiled-snapshot", "mission-contract", "output-path")

#: Every instant the fixtures use, so the ordering the freshness check depends on is readable in one
#: place. The plan is compiled at 04:00, and only a snapshot stated strictly after that is fresh.
AT_MISSION = "2026-08-19T03:00:00Z"
AT_COMPILE_SNAPSHOT = "2026-08-19T03:30:00Z"
AT_COMPILE = "2026-08-19T04:00:00Z"
AT_FRESH = "2026-08-19T04:30:00Z"
AT_SWAPPED = "2026-08-19T04:35:00Z"
AT_DIRTY = "2026-08-19T04:40:00Z"
AT_OCCUPIED = "2026-08-19T04:45:00Z"
AT_ARTIFACT = "2026-08-19T04:50:00Z"
AT_MOVED = "2026-08-19T04:55:00Z"
#: The worktree path the plan's second node claims, which the `occupied` capture really creates.
CLAIMED_WORKTREE = ".worktrees/wave-plan-admission"

NO_GIT = "a real git is required to capture a real PlanningSnapshot and compile a real WavePlan"
ROOT_FS = "a test that needs an unwritable directory cannot run as a user who ignores the mode bits"

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


#: `json.dumps` would write an already-overflowed Python `inf` as the TOKEN `Infinity`, which
#: `parse_constant` catches -- the wrong half of the defence. So the literal is spliced in as text: a
#: sentinel string is serialized normally and then replaced by the bare number, which is what puts an
#: ordinary JSON number that overflows DURING parsing in front of the post-parse walk.
OVERFLOW = "__OVERFLOWING_LITERAL__"


def overflowing(document: dict[str, Any]) -> str:
    text = json.dumps(document)
    assert f'"{OVERFLOW}"' in text, "the sentinel must survive serialization or the case proves nothing"
    return text.replace(f'"{OVERFLOW}"', "1e400")


def run(argv: list[str], *, cwd: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, capture_output=True, cwd=str(cwd), check=False, env=constructed_environment(extra))


# ---- the sibling fixtures, built once per run ----------------------------------------------------

FIXTURES: dict[str, Any] = {}
_SCRATCH: tempfile.TemporaryDirectory[str] | None = None


def _mission_body() -> dict[str, Any]:
    """One complete, valid MissionContract body in the shape `mission-contract.py` requires.

    Its ladder prefix and sorted stop-condition set are that tool's canonical forms; this body is an
    INPUT to it, and the sealed document this gate admits is whatever that tool emits from it.
    """
    return {
        "schema": MISSION_SCHEMA,
        "mission_id": MISSION_ID,
        "objective": "close slice 6 by admitting one compiled wave against current repository state",
        "scope": {
            "in_scope": ["skills/agentic-sdlc/tools/wave-plan-admission.py", "tests/test_wave_plan_admission.py"],
            "non_goals": ["the drift classifier", "the auto envelope"],
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


def _submissions_body() -> dict[str, Any]:
    """One valid workstream-submissions@1 body: an INPUT to the compiler, not to the gate.

    In the compiler's canonical forms -- workstreams ordered by id, every list a strictly ascending
    set -- because a body that is not in them would be refused there and this module would never get a
    compiled plan to admit.
    """
    return {
        "schema": SUBMISSIONS_SCHEMA,
        "submission_id": "submissions-slice-6-t6",
        "mission_id": MISSION_ID,
        "stated_at": "2026-08-19T03:45:00Z",
        "declared_concurrency": 2,
        "workstreams": [
            {
                "id": "ws-a-cartography",
                "objective": "map the planning artifact chain's existing tools and their digests",
                "authority_class": "read-only-advisory",
                "capability_demands": ["repository-read"],
                "dependencies": [],
                "file_custody": [],
                "worktree_custody": None,
            },
            {
                "id": "ws-b-admission",
                "objective": "build the plan admission gate and its tests",
                "authority_class": "owned-worktree-write",
                "capability_demands": ["git-worktree-write", "python-execution"],
                "dependencies": ["ws-a-cartography"],
                "file_custody": [
                    "skills/agentic-sdlc/tools/wave-plan-admission.py",
                    "tests/test_wave_plan_admission.py",
                ],
                "worktree_custody": ".worktrees/wave-plan-admission",
            },
        ],
    }


def _sibling(argv: list[str], scratch: Path, expected: str, label: str) -> dict[str, Any]:
    """Run one sibling tool and demand its own success verdict. A failure here is raised, not skipped.

    A sibling that cannot seal its own valid input is a real regression, and swallowing it would
    silently delete this module's admission coverage.
    """
    done = run([sys.executable, "-B", *argv], cwd=scratch)
    if done.returncode != EXIT_OK:
        raise AssertionError(f"{label} failed: exit {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != expected:
        raise AssertionError(f"{label} refused a valid input: {result['reasons']}")
    return result


GIT_ENVIRONMENT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(repository: Path, *args: str) -> None:
    """One git command against a scratch repository, with every ambient config file taken away."""
    step = run(["git", *args], cwd=repository, extra=GIT_ENVIRONMENT)
    if step.returncode != 0:
        raise AssertionError(f"git {args} in {repository} failed: {step.stderr!r}")


def _commit(repository: Path, message: str) -> None:
    _git(repository, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", message)


def _capture(repository: Path, scratch: Path, name: str, at: str) -> None:
    """Capture ONE real snapshot of the repository as it is right now, and remember its digest."""
    target = scratch / f"{name}.json"
    result = _sibling(
        [str(SNAPSHOT_TOOL), "capture", "--repository", str(repository), "--at", at, "--out", str(target)],
        scratch,
        "captured",
        f"planning-snapshot.py capture ({name})",
    )
    FIXTURES[name] = target
    FIXTURES[f"{name}_digest"] = result["digest"]


def setUpModule() -> None:
    """Build every fixture ONCE by running the real tools against one really-mutated repository.

    The order is load-bearing and reads as a timeline: observe, compile, then observe again after each
    single change, so every capture differs from `compiled` in exactly one dimension. `.gitignore`
    lands in the first commit so that adding a worktree or a wave artifact later does not ALSO dirty
    the tree -- otherwise the occupancy and prior-effect fixtures would each carry two blockers and
    neither case would be attributable.
    """
    global _SCRATCH
    _SCRATCH = tempfile.TemporaryDirectory(prefix="wave-plan-admission-fixtures-")
    scratch = Path(_SCRATCH.name).resolve()
    FIXTURES["scratch"] = scratch

    body = scratch / "mission-body.json"
    body.write_text(json.dumps(_mission_body(), indent=2), encoding="utf-8")
    result = _sibling(
        [str(MISSION_TOOL), "define", "--contract", str(body)], scratch, "defined", "mission-contract.py define"
    )
    mission = scratch / "mission.json"
    mission.write_bytes(canonical(result["contract"]))
    FIXTURES["mission"] = mission
    FIXTURES["mission_digest"] = result["digest"]

    if shutil.which("git") is None:
        return
    repository = scratch / "repo"
    repository.mkdir()
    (repository / "tracked.txt").write_text("one\n", encoding="utf-8")
    (repository / ".gitignore").write_text(".worktrees/\n.sdlc/\n", encoding="utf-8")
    _git(repository, "init", "--quiet", "-b", "trunk", ".")
    _git(repository, "add", "tracked.txt", ".gitignore")
    _commit(repository, "one")
    FIXTURES["repository"] = repository

    _capture(repository, scratch, "compiled", AT_COMPILE_SNAPSHOT)
    submissions = scratch / "submissions.json"
    submissions.write_bytes(canonical(seal(_submissions_body())))
    plan = scratch / "plan.json"
    result = _sibling(
        [
            str(COMPILER_TOOL), "compile",
            "--mission", str(mission), "--snapshot", str(FIXTURES["compiled"]), "--submissions", str(submissions),
            "--at", AT_COMPILE, "--out", str(plan),
        ],
        scratch,
        "compiled",
        "wave-plan-compiler.py compile",
    )
    FIXTURES["plan"] = plan
    FIXTURES["plan_digest"] = result["plan_digest"]

    # Same head, captured AT the compile instant: the freshness triple's equal-time member.
    _capture(repository, scratch, "equal", AT_COMPILE)
    # Same head, captured later: the one input set that reaches `admitted`.
    _capture(repository, scratch, "fresh", AT_FRESH)

    # A real clone: the SAME commit and tree, in a different physical repository. Only identity moves.
    _git(scratch, "clone", "--quiet", str(repository), "swapped-repo")
    _capture(scratch / "swapped-repo", scratch, "swapped", AT_SWAPPED)

    untracked = repository / "someone-elses-work.txt"
    untracked.write_text("uncommitted\n", encoding="utf-8")
    _capture(repository, scratch, "dirty", AT_DIRTY)
    untracked.unlink()

    _git(repository, "worktree", "add", "--quiet", "-b", "custody-holder", CLAIMED_WORKTREE)
    _capture(repository, scratch, "occupied", AT_OCCUPIED)
    _git(repository, "worktree", "remove", CLAIMED_WORKTREE)

    artifact = repository / ".sdlc" / "wave-journal.json"
    artifact.parent.mkdir()
    artifact.write_text('{"wave":"one"}\n', encoding="utf-8")
    _capture(repository, scratch, "artifact", AT_ARTIFACT)
    shutil.rmtree(artifact.parent)

    (repository / "tracked.txt").write_text("two\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _commit(repository, "two")
    _capture(repository, scratch, "moved", AT_MOVED)


def tearDownModule() -> None:
    if _SCRATCH is not None:
        _SCRATCH.cleanup()


# ---- mutation helpers ----------------------------------------------------------------------------


def at_path(document: dict[str, Any], dotted: str) -> tuple[Any, str]:
    """Walk a dotted path to its container and final key. `nodes.0.node_id` indexes a list."""
    container: Any = document
    parts = dotted.split(".")
    for part in parts[:-1]:
        container = container[int(part)] if isinstance(container, list) else container[part]
    return container, parts[-1]


def put(document: dict[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    """Set one dotted field on a DEEP COPY, so one test's mutation cannot leak into another's."""
    copied = copy.deepcopy(document)
    container, key = at_path(copied, dotted)
    if isinstance(container, list):
        container[int(key)] = value
    else:
        container[key] = value
    return copied


def drop(document: dict[str, Any], dotted: str) -> dict[str, Any]:
    """Remove one dotted field on a DEEP COPY."""
    copied = copy.deepcopy(document)
    container, key = at_path(copied, dotted)
    if isinstance(container, list):
        del container[int(key)]
    else:
        del container[key]
    return copied


class ToolCase(unittest.TestCase):
    """One private working directory per test, with the three sealed inputs copied into it.

    Copied rather than shared: several tests mutate an input, and a shared fixture file would make the
    order tests run in load-bearing.
    """

    needs_git = True

    #: The working copy's name for each fixture. `snapshot.json` is the FRESH capture, because that is
    #: the document `--fresh-snapshot` consumes and the one most cases mutate; the alternative captures
    #: keep their own names so a test can name the observation it wants in one word.
    COPIES = {
        "mission": "mission",
        "plan": "plan",
        "compiled": "compiled",
        "snapshot": "fresh",
        "equal": "equal",
        "swapped": "swapped",
        "dirty": "dirty",
        "occupied": "occupied",
        "artifact": "artifact",
        "moved": "moved",
    }

    @classmethod
    def setUpClass(cls) -> None:
        if cls.needs_git and "plan" not in FIXTURES:
            raise unittest.SkipTest(NO_GIT)

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="wave-plan-admission-case-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        for name, fixture in self.COPIES.items():
            source = FIXTURES.get(fixture)
            if source is not None:
                shutil.copy2(source, self.work / f"{name}.json")

    def read(self, name: str) -> dict[str, Any]:
        return json.loads((self.work / f"{name}.json").read_text(encoding="utf-8"))

    def write(self, name: str, document: dict[str, Any]) -> Path:
        target = self.work / f"{name}.json"
        target.write_bytes(canonical(document))
        return target

    def invoke(self, *argv: str, extra: dict[str, str] | None = None, cwd: Path | None = None) -> Any:
        """Run the tool and return (exit code, parsed result or None, stderr text)."""
        done = run([sys.executable, "-B", str(TOOL), *argv], cwd=cwd or self.work, extra=extra)
        stderr = done.stderr.decode("utf-8", "replace")
        payload = done.stdout.decode("utf-8")
        result: dict[str, Any] | None = None
        if payload:
            try:
                result = json.loads(payload)
            except ValueError:  # a result document that is not one JSON object is itself a failure
                self.fail(f"stdout is not one JSON document: {payload[:400]!r}")
        return done.returncode, result, stderr

    def admit(
        self,
        *extra_argv: str,
        at: str = AT,
        out: str | None = None,
        cwd: Path | None = None,
        fresh: str = "snapshot.json",
        compiled: str | None = "compiled.json",
    ) -> Any:
        """The whole admissible invocation, with the compile-time snapshot supplied by DEFAULT.

        Supplied by default because it is what the admitting path needs: without it physical target
        identity is undecidable and the disposition is `blocked`, which is its own named case below
        rather than the baseline every other case would then have to work around.
        """
        argv = [
            "admit",
            "--plan", "plan.json",
            "--fresh-snapshot", fresh,
            "--mission", "mission.json",
            "--at", at,
        ]
        if compiled is not None:
            argv += ["--compiled-snapshot", compiled]
        if out is not None:
            argv += ["--out", out]
        return self.invoke(*argv, *extra_argv, cwd=cwd)

    def mutate_and_admit(
        self, name: str, mutation: dict[str, Any] | None = None, *, reseal: bool, **kwargs: Any
    ) -> Any:
        """Write one mutated input and admit. `reseal` decides WHICH guard the case can reach.

        A shape mutation must be resealed, because `_sealed_input` stops at the first failure in the
        order schema, keys, digest: an unresealed shape mutation would only ever produce the digest
        reason, and the shape guard under test would never run.
        """
        document = mutation if mutation is not None else self.read(name)
        self.write(name, seal(document) if reseal else document)
        return self.admit(**kwargs)

    # ---- the shared assertions --------------------------------------------------------------------

    def assert_admitted(self, result: dict[str, Any]) -> dict[str, Any]:
        """The POSITIVE CONTROL: no reason at all, six met checks, one sealed admitted report.

        Tolerating a subset of reasons would let every negative case in this module rot silently, so
        this asserts the reason list is EXACTLY empty and every check that ran is met.
        """
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        self.assertEqual(result["command"], "admit")
        self.assertIs(result["inputs_admitted"], True)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["verdict"], ADMITTED)
        report = result["report"]
        self.assertIsNotNone(report)
        self.assertEqual(report["schema"], ADMISSION_SCHEMA)
        self.assertEqual(report["disposition"], ADMITTED)
        self.assertEqual([entry["slug"] for entry in report["checks"]], list(RAN_SLUGS))
        self.assertTrue(all(entry["met"] and entry["blockers"] == [] for entry in report["checks"]))
        self.assertEqual(result["report_digest"], expected_digest(report))
        self.assertEqual(report["digest"], expected_digest(report))
        return report

    def assert_blocked(self, result: dict[str, Any], slug: str, *fragments: str) -> dict[str, Any]:
        """A CHECK refused: the inputs were admitted, the report IS sealed, and it says `blocked`.

        This is the shape issue 16 line 130 asks for -- "a content-minimized receipt OR EXACT
        BLOCKERS" -- so the assertions are the mirror image of `assert_refused_input`: a report exists,
        it re-derives its own digest, and the named group carries the reason.
        """
        self.assertIs(result["inputs_admitted"], True)
        self.assertEqual(result["verdict"], REFUSED)
        report = result["report"]
        self.assertIsNotNone(report, "an admitted input set must still seal the report that says no")
        self.assertEqual(report["disposition"], BLOCKED)
        self.assertEqual(report["digest"], expected_digest(report))
        groups = {entry["slug"]: entry for entry in report["checks"]}
        self.assertIn(slug, groups)
        self.assertFalse(groups[slug]["met"])
        joined = " ".join(groups[slug]["blockers"])
        for fragment in fragments:
            self.assertIn(fragment, joined)
        # The result's own reasons are generated from the same store, so the two cannot disagree.
        self.assertEqual(sorted(result["reasons"]), sorted(sum((entry["blockers"] for entry in report["checks"]), [])))
        return report

    def assert_only_blocked_check(self, result: dict[str, Any], slug: str, *fragments: str) -> dict[str, Any]:
        """`assert_blocked`, plus: EVERY OTHER check is met, so the case is attributable to one thing."""
        report = self.assert_blocked(result, slug, *fragments)
        unmet = [entry["slug"] for entry in report["checks"] if not entry["met"]]
        self.assertEqual(unmet, [slug], f"exactly one check may be unmet here, found {unmet}")
        return report

    def assert_refused_input(self, result: dict[str, Any], slug: str, *fragments: str) -> None:
        """An inadmissible input: nothing sealed, nothing written, and the field named in its group."""
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIs(result["inputs_admitted"], False)
        self.assertIsNone(result["report"])
        self.assertIsNone(result["report_digest"])
        self.assertIsNone(result["inputs"])
        self.assertIsNone(result["out"])
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn(slug, groups)
        self.assertFalse(groups[slug]["met"])
        joined = " ".join(groups[slug]["reasons"])
        for fragment in fragments:
            self.assertIn(fragment, joined)
        # No CURRENT-STATE check may have noted anything: they run only over admitted inputs, so a
        # refusal here means none of them was reached, and one that spoke anyway read an unread field.
        spoke = {entry["slug"] for entry in result["checks"] if entry["reasons"]}
        self.assertEqual(spoke - set(INPUT_SLUGS), set())


class AdmittedInputSetTests(ToolCase):
    """The positive control itself, and what the sealed report says about the admitted inputs."""

    def test_the_unmutated_input_set_is_admitted_and_seals_one_admitted_report(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_the_report_binds_the_three_input_digests_the_siblings_derived(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        self.assertEqual(
            report["inputs"],
            {
                "mission_digest": FIXTURES["mission_digest"],
                "plan_digest": FIXTURES["plan_digest"],
                "snapshot_digest": FIXTURES["fresh_digest"],
            },
        )
        self.assertEqual(result["inputs"], report["inputs"])
        # The FRESH capture's digest, never the compile-time one the plan records: an admitted report
        # binds the observation the checks were run against.
        self.assertNotEqual(report["inputs"]["snapshot_digest"], FIXTURES["compiled_digest"])
        self.assertEqual(self.read("plan")["inputs"]["snapshot_digest"], FIXTURES["compiled_digest"])

    def test_the_report_records_the_fresh_snapshots_own_head_and_instant_verbatim(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        snapshot = self.read("snapshot")
        self.assertEqual(report["observed"]["head"], snapshot["head"])
        self.assertEqual(report["observed"]["snapshot_stated_at"], snapshot["stated_at"])
        self.assertEqual(report["admitted_at"], AT)

    def test_the_report_is_content_minimized_and_carries_no_plan_content(self) -> None:
        """No node, edge, custody path, or objective reaches the report: the digest is the binding."""
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        self.assertEqual(
            sorted(report),
            [
                "admitted_at", "checks", "deferred_dimensions", "digest", "disposition", "inputs",
                "mission_id", "observed", "plan_revision", "schema",
            ],
        )
        rendered = canonical(report).decode("ascii")
        plan = self.read("plan")
        for node in plan["nodes"]:
            self.assertNotIn(node["node_id"], rendered)
            self.assertNotIn(node["objective"], rendered)
            for path in node["file_custody"]:
                self.assertNotIn(path, rendered)
        self.assertNotIn(CLAIMED_WORKTREE, rendered)
        self.assertEqual(report["mission_id"], plan["mission_id"])
        self.assertEqual(report["plan_revision"], plan["revision"])

    def test_the_report_names_every_check_that_ran_and_none_that_did_not(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        named = [entry["slug"] for entry in report["checks"]]
        self.assertEqual(named, list(RAN_SLUGS))
        # The reserved group slug is never emitted now that each check is named individually, and no
        # deferred dimension appears as a check: that pairing is what makes `met` mean something.
        self.assertNotIn(GROUP_SLUG, named)
        self.assertEqual(set(named) & set(DEFERRED_NAMES), set())
        self.assertEqual(set(named) - set(ISSUE_16_SLUGS), set())

    def test_the_report_defers_every_dimension_it_does_not_decide_with_a_reason_each(self) -> None:
        """The other half of "never vacuously met": what was not decided is named, not omitted."""
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        deferred = report["deferred_dimensions"]
        self.assertEqual([entry["dimension"] for entry in deferred], list(DEFERRED_NAMES))
        self.assertEqual([entry["dimension"] for entry in deferred], sorted(entry["dimension"] for entry in deferred))
        for entry in deferred:
            self.assertEqual(sorted(entry), ["dimension", "reason"])
            self.assertGreater(len(entry["reason"]), 40, entry)
        # Every whole dimension of issue 16's eleven is either a check that ran or a deferred one:
        # neither list may quietly lose a member.
        whole = {name for name in DEFERRED_NAMES if ":" not in name}
        self.assertEqual(whole | set(RAN_SLUGS), set(ISSUE_16_SLUGS))

    def test_the_result_reports_the_five_input_groups_and_the_six_checks(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual([entry["slug"] for entry in result["checks"]], [*INPUT_SLUGS, *RAN_SLUGS])
        # `verify`'s own groups are absent: reporting them as met would claim a check that never ran.
        self.assertNotIn("digest", {entry["slug"] for entry in result["checks"]})

    def test_every_residual_is_carried_in_the_result(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        joined = " ".join(result["residuals"])
        for fragment in (
            "re-derivation",
            "deferred_dimensions",
            "CALLER's claim",
            "COUNTS",
            "compile-time snapshot",
            "admitted is NOT approved",
        ):
            self.assertIn(fragment, joined)
        # The Phase A stub residual is GONE, and so is every claim that a check does not run.
        self.assertNotIn("PHASE A", joined)


class ProseCountTests(ToolCase):
    """Every count the tool's own prose states, checked against the count its report DERIVES.

    This class exists because a count written in prose is a checkable assertion that nothing checks:
    this very file shipped a tool whose docstring, residual, help text, and two comments all said
    "three refinements" while `DEFERRED_DIMENSIONS` carried five, and every one of the 134 tests
    passed. The numbers are derived from the sealed report rather than re-expressed here, so a
    revision that decides a deferred dimension has to update the prose in the same change.
    """

    #: Each claim, as the pattern that finds EVERY site of it. `{words}` is filled with the number
    #: word alternation. The ran-check pattern admits only a CLOSED set of adjectives between the
    #: number and `checks`, because an open `[a-z-]+` gap also matches "five refinements of checks",
    #: which states the refinement count and not the ran one; and the literal space before `checks`
    #: is what keeps "TWO cross-checks" -- a claim about something else entirely -- out of both.
    CLAIMS = {
        "refinements": r"\b({words})\b (?:partial )?refinements\b",
        "whole": r"\b({words})\b whole dimensions\b",
        "ran": r"\b({words})\b(?: (?:met|unmet|implemented|decidable|current-state)){{0,2}} checks\b",
    }
    WORDS = (
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    )

    def claimed(self, text: str, claim: str) -> list[int]:
        """Every number the prose states for one claim, as integers, in source order."""
        pattern = re.compile(self.CLAIMS[claim].format(words="|".join(self.WORDS)), re.IGNORECASE)
        return [self.WORDS.index(match.group(1).lower()) + 1 for match in pattern.finditer(text)]

    def test_every_count_the_prose_claims_is_the_count_the_report_derives(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        dimensions = [entry["dimension"] for entry in report["deferred_dimensions"]]
        derived = {
            "ran": len(report["checks"]),
            "whole": len([name for name in dimensions if ":" not in name]),
            "refinements": len([name for name in dimensions if ":" in name]),
        }
        # The readiness reference restates these counts for consumers, so it rots the same way the
        # tool's own prose does (agentic-sdlc-bfea landed exactly that rot); scan both together.
        reference = ROOT / "skills" / "agentic-sdlc" / "references" / "readiness-composition.md"
        source = TOOL.read_text(encoding="utf-8") + reference.read_text(encoding="utf-8")
        for claim, count in derived.items():
            found = self.claimed(source, claim)
            # A claim site that VANISHED is its own failure: an unstated count cannot be checked, and
            # silently scanning zero sites is how this class would stop proving anything.
            self.assertGreaterEqual(len(found), 1, f"the prose states no {claim} count at all")
            self.assertEqual(
                set(found),
                {count},
                f"the prose states {sorted(set(found))} for {claim} and the sealed report derives {count}",
            )

    def test_the_scan_catches_a_rotted_count(self) -> None:
        """The POSITIVE CONTROL for the scan above, over prose this test rots on purpose.

        Without it, a pattern that silently stopped matching would make the assertion above vacuous
        and every count in the file could drift again.
        """
        source = TOOL.read_text(encoding="utf-8")
        for claim, wrong in (
            ("refinements", "seven partial refinements"),
            ("whole", "nine whole dimensions"),
            ("ran", "ten current-state checks"),
        ):
            original = self.claimed(source, claim)
            self.assertTrue(original, f"the {claim} claim must be findable before it can be rotted")
            rotted = re.sub(
                self.CLAIMS[claim].format(words="|".join(self.WORDS)), wrong, source, count=1, flags=re.IGNORECASE
            )
            self.assertNotEqual(rotted, source)
            self.assertIn(self.WORDS.index(wrong.split()[0]) + 1, self.claimed(rotted, claim))


class InputAdmissionTests(ToolCase):
    """One case per named refusal, each starting from the control the class above asserts."""

    def test_a_wrong_schema_string_is_refused_per_input_position(self) -> None:
        for name, slug, schema in (
            ("plan", "wave-plan", PLAN_SCHEMA),
            ("snapshot", "planning-snapshot", SNAPSHOT_SCHEMA),
            ("mission", "mission-contract", MISSION_SCHEMA),
        ):
            with self.subTest(input=name):
                self.setUp()
                document = put(self.read(name), "schema", "agentic-sdlc/not-that-kind@1")
                code, result, _ = self.mutate_and_admit(name, document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, slug, "agentic-sdlc/not-that-kind@1", schema)

    def test_an_unrecognised_key_is_refused_rather_than_ignored_per_input_position(self) -> None:
        for name, slug in (("plan", "wave-plan"), ("snapshot", "planning-snapshot"), ("mission", "mission-contract")):
            with self.subTest(input=name):
                self.setUp()
                document = put(self.read(name), "surprise", "a field this revision does not know")
                code, result, _ = self.mutate_and_admit(name, document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, slug, "closed sealed key set", "'surprise'")

    def test_a_missing_top_level_key_is_refused_per_input_position(self) -> None:
        for name, slug, key in (
            ("plan", "wave-plan", "limits"),
            ("snapshot", "planning-snapshot", "worktrees"),
            ("mission", "mission-contract", "constraints"),
        ):
            with self.subTest(input=name):
                self.setUp()
                code, result, _ = self.mutate_and_admit(name, drop(self.read(name), key), reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, slug, "closed sealed key set", f"'{key}'")

    def test_a_digest_its_content_does_not_re_derive_is_refused_per_input_position(self) -> None:
        """NOT resealed on purpose: this is the one case where the stale digest IS the mutation."""
        for name, slug, field, value in (
            ("plan", "wave-plan", "compiled_at", "2026-08-19T04:00:01Z"),
            ("snapshot", "planning-snapshot", "stated_at", "2026-08-19T03:30:01Z"),
            ("mission", "mission-contract", "objective", "a different objective entirely"),
        ):
            with self.subTest(input=name):
                self.setUp()
                original = self.read(name)
                document = put(original, field, value)
                code, result, _ = self.mutate_and_admit(name, document, reseal=False)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(
                    result, slug, original["digest"], expected_digest(document), "does not re-derive"
                )

    def test_a_digest_that_is_not_a_sha256_is_refused(self) -> None:
        document = put(self.read("plan"), "digest", "not-a-digest")
        code, result, _ = self.mutate_and_admit("plan", document, reseal=False)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "wave-plan", "64 lowercase hexadecimal", "recorded digest")

    def test_an_uppercase_digest_is_refused_because_one_value_has_one_spelling(self) -> None:
        original = self.read("plan")
        document = put(original, "digest", original["digest"].upper())
        code, result, _ = self.mutate_and_admit("plan", document, reseal=False)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "wave-plan", "64 lowercase hexadecimal")

    def test_a_consumed_nested_field_that_is_absent_cannot_be_defaulted(self) -> None:
        for name, slug, dotted in (
            ("plan", "wave-plan", "inputs.mission_digest"),
            ("snapshot", "planning-snapshot", "repository.worktree_path"),
            ("mission", "mission-contract", "authority.ceiling"),
        ):
            with self.subTest(field=dotted):
                self.setUp()
                code, result, _ = self.mutate_and_admit(name, drop(self.read(name), dotted), reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, slug, f"has no {dotted}", "cannot be defaulted")

    def test_a_consumed_field_recorded_as_empty_states_nothing(self) -> None:
        code, result, _ = self.mutate_and_admit("plan", put(self.read("plan"), "nodes", []), reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "wave-plan", "records nodes as empty", "states nothing")

    def test_an_empty_edge_list_is_admitted_because_a_one_node_wave_has_none(self) -> None:
        """The positive half of the check above: `edges` is deliberately NOT a required field."""
        plan = self.read("plan")
        plan = put(plan, "edges", [])
        plan = put(plan, "nodes.1.dependencies", [])
        code, result, _ = self.mutate_and_admit("plan", plan, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_mission_id_that_is_not_an_identifier_is_refused(self) -> None:
        code, result, _ = self.mutate_and_admit("plan", put(self.read("plan"), "mission_id", "two words"), reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "wave-plan", "'two words'", "unreserved characters")

    def test_a_plan_revision_below_one_is_refused(self) -> None:
        for value in (0, -1, True, 1.0, "1"):
            with self.subTest(revision=value):
                self.setUp()
                code, result, _ = self.mutate_and_admit("plan", put(self.read("plan"), "revision", value), reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, "wave-plan", "integer of at least 1")

    def test_a_malformed_recorded_instant_is_refused(self) -> None:
        code, result, _ = self.mutate_and_admit(
            "snapshot", put(self.read("snapshot"), "stated_at", "2026-08-19 03:30:00"), reseal=True
        )
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "planning-snapshot", "YYYY-MM-DDTHH:MM:SSZ")

    def test_a_head_that_is_not_the_closed_key_set_is_refused(self) -> None:
        for name, slug in (("plan", "wave-plan"), ("snapshot", "planning-snapshot")):
            with self.subTest(input=name):
                self.setUp()
                document = put(self.read(name), "head.extra", "a fourth head field")
                code, result, _ = self.mutate_and_admit(name, document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, slug, "closed key set", "'extra'")

    def test_a_head_object_name_that_is_not_a_git_object_name_is_refused(self) -> None:
        for dotted in ("head.commit_sha", "head.tree_sha"):
            with self.subTest(field=dotted):
                self.setUp()
                document = put(self.read("snapshot"), dotted, "z" * 40)
                code, result, _ = self.mutate_and_admit("snapshot", document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, "planning-snapshot", "git object name", dotted.split(".")[1])

    def test_a_sha256_object_name_is_admitted_because_the_object_format_is_the_repositorys_choice(self) -> None:
        """The positive half: 64 hex characters is a valid object name, not a digest in the wrong field.

        BOTH heads are moved to the sha256-shaped name, because the freshness check compares them: a
        one-sided mutation would be refused for having moved rather than for its object format, and
        this case would stop testing the format at all.
        """
        self.write("snapshot", seal(put(self.read("snapshot"), "head.commit_sha", "c" * 64)))
        plan = put(self.read("plan"), "head.commit_sha", "c" * 64)
        code, result, _ = self.mutate_and_admit("plan", plan, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_an_empty_branch_string_records_nothing_while_null_records_a_detached_head(self) -> None:
        document = put(self.read("snapshot"), "head.branch", "")
        code, result, _ = self.mutate_and_admit("snapshot", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "planning-snapshot", "neither null nor a non-empty string")

        self.setUp()
        # Detached in BOTH records, for the same reason as the case above: a head that is detached now
        # and was on a branch at compile time is a MOVED head, which is a different refusal.
        self.write("snapshot", seal(put(self.read("snapshot"), "head.branch", None)))
        code, result, _ = self.mutate_and_admit("plan", put(self.read("plan"), "head.branch", None), reseal=True)
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        self.assertIsNone(report["observed"]["head"]["branch"])

    def test_two_inadmissible_inputs_are_both_named_in_their_own_groups(self) -> None:
        """One mistake per group, so a caller learns about both rather than only the first."""
        self.write("plan", seal(put(self.read("plan"), "schema", "agentic-sdlc/wrong@1")))
        self.write("mission", seal(put(self.read("mission"), "schema", "agentic-sdlc/wrong@1")))
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertFalse(groups["wave-plan"]["met"])
        self.assertFalse(groups["mission-contract"]["met"])
        self.assertTrue(groups["planning-snapshot"]["met"])
        self.assertIsNone(result["report"])


class SnapshotFreshnessTests(ToolCase):
    """The 5ee7 anchor, proved against REAL captures of a repository that really moved.

    The triple issue 16 turns on is here: the same head captured later ADMITS, a moved head REFUSES,
    and a capture stated at exactly the compile instant REFUSES. All three snapshots come out of
    `planning-snapshot.py capture` against one scratch repository, so what is being checked is a
    comparison of two real observations rather than two strings a test wrote.
    """

    def test_the_same_head_captured_later_is_fresh(self) -> None:
        """The POSITIVE CONTROL of the pair: nothing moved, the capture is later, admission passes."""
        self.assertEqual(self.read("snapshot")["head"], self.read("plan")["head"])
        self.assertGreater(self.read("snapshot")["stated_at"], self.read("plan")["compiled_at"])
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_head_that_really_moved_refuses_and_names_both_object_names(self) -> None:
        """The REFUSING half: one more real commit, one more real capture, and the plan is stale."""
        moved, plan = self.read("moved"), self.read("plan")
        self.assertNotEqual(moved["head"]["commit_sha"], plan["head"]["commit_sha"])
        code, result, _ = self.admit(fresh="moved.json")
        self.assertEqual(code, EXIT_OK)
        report = self.assert_only_blocked_check(
            result,
            "snapshot-freshness",
            plan["head"]["commit_sha"],
            moved["head"]["commit_sha"],
            "the target moved after this plan was compiled",
        )
        # Both object names moved with the commit, so both are named: a consumer diagnosing this needs
        # to see that the tree changed too, not only that a ref was repointed.
        blockers = " ".join(report["checks"][0]["blockers"])
        self.assertIn("head.commit_sha", blockers)
        self.assertIn("head.tree_sha", blockers)

    def test_a_capture_stated_at_the_compile_instant_is_not_strictly_later(self) -> None:
        """The EQUAL-TIME member: same head, real capture, stated at exactly the plan's compiled_at."""
        equal = self.read("equal")
        self.assertEqual(equal["head"], self.read("plan")["head"])
        self.assertEqual(equal["stated_at"], self.read("plan")["compiled_at"])
        code, result, _ = self.admit(fresh="equal.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "snapshot-freshness", "is not strictly later", AT_COMPILE
        )

    def test_a_branch_that_moved_alone_refuses_even_though_the_commit_matches(self) -> None:
        """`head` is three fields, and the branch is one of them: a checkout that switched branches is
        a different custody situation even at the same commit."""
        document = put(self.read("snapshot"), "head.branch", "somewhere-else")
        code, result, _ = self.mutate_and_admit("snapshot", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(result, "snapshot-freshness", "head.branch", "somewhere-else")

    def test_an_admission_instant_before_the_observation_refuses(self) -> None:
        code, result, _ = self.admit(at=AT_COMPILE)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "snapshot-freshness", "--at", "is earlier than", AT_FRESH
        )

    def test_an_admission_instant_equal_to_the_observation_is_admitted(self) -> None:
        """The positive half: capturing and admitting inside one second is honest, not stale."""
        code, result, _ = self.admit(at=AT_FRESH)
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_the_compile_time_snapshot_supplied_as_the_fresh_one_proves_nothing_and_refuses(self) -> None:
        """A fresh capture is a SECOND observation, not the first one handed over twice."""
        code, result, _ = self.admit(fresh="compiled.json")
        self.assertEqual(code, EXIT_OK)
        report = self.assert_only_blocked_check(
            result, "snapshot-freshness", "IS the snapshot this plan was compiled from", FIXTURES["compiled_digest"]
        )
        blockers = report["checks"][0]["blockers"]
        # TWO independent reasons, because the digest identity and the instant ordering are different
        # facts and a caller that fixes only the timestamp must still be refused.
        self.assertEqual(len(blockers), 2, blockers)
        self.assertIn("is not strictly later", " ".join(blockers))


class TargetIdentityTests(ToolCase):
    """Physical target identity, proved against a REAL clone that carries the very same commit."""

    def test_the_same_repository_re_observed_keeps_identity_met(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_real_clone_at_the_same_commit_is_a_different_physical_target(self) -> None:
        """The swapped-repository case, and the reason freshness alone is not enough: `git clone`
        reproduces the commit, the tree, and the branch, so every head field matches and ONLY the
        physical repository differs."""
        swapped, compiled = self.read("swapped"), self.read("compiled")
        self.assertEqual(swapped["head"], self.read("plan")["head"])
        self.assertNotEqual(swapped["repository"]["worktree_path"], compiled["repository"]["worktree_path"])
        code, result, _ = self.admit(fresh="swapped.json")
        self.assertEqual(code, EXIT_OK)
        report = self.assert_only_blocked_check(
            result,
            "target-and-custody-identity",
            "repository.worktree_path",
            "not the same physical target",
            swapped["repository"]["worktree_path"],
        )
        blockers = " ".join(report["checks"][1]["blockers"])
        self.assertIn("repository.git_dir", blockers)
        self.assertIn("repository.git_dir_inode", blockers)
        # Freshness is MET here, which is the whole point of keeping the two checks apart.
        groups = {entry["slug"]: entry for entry in report["checks"]}
        self.assertTrue(groups["snapshot-freshness"]["met"])

    def test_an_absent_compile_time_snapshot_refuses_rather_than_passing(self) -> None:
        """The conservative direction: an unverifiable identity is not a verified one."""
        code, result, _ = self.admit(compiled=None)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "target-and-custody-identity",
            "was not supplied",
            "--compiled-snapshot",
            self.read("plan")["inputs"]["snapshot_digest"],
        )

    def test_a_compile_time_snapshot_the_plan_does_not_bind_is_refused(self) -> None:
        """Comparing identity against the wrong pair of observations is worse than not comparing it."""
        code, result, _ = self.admit(compiled="snapshot.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "target-and-custody-identity",
            "is not the snapshot the plan was compiled from",
            FIXTURES["fresh_digest"],
            FIXTURES["compiled_digest"],
        )

    def test_a_reused_path_with_a_different_inode_is_refused(self) -> None:
        """A repository deleted and recreated at the same path is a different target, and the inode is
        the only field that says so."""
        original = self.read("snapshot")
        document = put(original, "repository.git_dir_inode", original["repository"]["git_dir_inode"] + 1)
        code, result, _ = self.mutate_and_admit("snapshot", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(result, "target-and-custody-identity", "repository.git_dir_inode")

    def test_an_inadmissible_compile_time_snapshot_seals_nothing(self) -> None:
        """The optional input is still an INPUT: a supplied document that is not one refuses early."""
        self.write("compiled", seal(put(self.read("compiled"), "schema", "agentic-sdlc/wrong@1")))
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "compiled-snapshot", "agentic-sdlc/wrong@1", SNAPSHOT_SCHEMA)


class CustodyAvailabilityTests(ToolCase):
    """Worktree occupancy decided exactly, dirty state refused conservatively."""

    def test_a_clean_repository_with_no_claimed_worktree_is_available(self) -> None:
        """The POSITIVE CONTROL, and it is not vacuous: the snapshot really does list a worktree -- the
        main one -- so the comparison ran and excluded the checkout itself."""
        snapshot = self.read("snapshot")
        self.assertEqual(
            [entry["path"] for entry in snapshot["worktrees"]], [snapshot["repository"]["worktree_path"]]
        )
        self.assertEqual([snapshot["dirty_state"][key] for key in ("staged", "unmerged", "unstaged", "untracked")],
                         [0, 0, 0, 0])
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_real_worktree_at_the_claimed_path_refuses_and_names_it(self) -> None:
        """A real `git worktree add` at exactly the path the plan's second node claims."""
        occupied = self.read("occupied")
        self.assertEqual(len(occupied["worktrees"]), 2)
        code, result, _ = self.admit(fresh="occupied.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "dependency-and-artifact-availability",
            "ws-b-admission",
            CLAIMED_WORKTREE,
            "custody-holder",
            "cannot take custody of a worktree that exists",
        )

    def test_a_real_untracked_file_refuses_because_dirty_state_records_counts(self) -> None:
        """The conservative half, bounded to what `dirty_state` actually is: four counts, no paths."""
        dirty = self.read("dirty")
        self.assertEqual(dirty["dirty_state"]["untracked"], 1)
        code, result, _ = self.admit(fresh="dirty.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "dependency-and-artifact-availability",
            "untracked=1",
            "records COUNTS rather than paths",
            "undecidable disjointness refuses",
        )
        # The blocker must NOT claim a path comparison it could not have made.
        report = result["report"]
        groups = {entry["slug"]: entry for entry in report["checks"]}
        self.assertNotIn("someone-elses-work.txt", " ".join(groups["dependency-and-artifact-availability"]["blockers"]))

    def test_every_dirty_dimension_refuses_by_its_own_name(self) -> None:
        for key in ("staged", "unmerged", "unstaged", "untracked"):
            with self.subTest(dimension=key):
                self.setUp()
                document = put(self.read("snapshot"), f"dirty_state.{key}", 3)
                code, result, _ = self.mutate_and_admit("snapshot", document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_only_blocked_check(result, "dependency-and-artifact-availability", f"{key}=3")

    def test_a_worktree_elsewhere_in_the_repository_is_not_occupancy(self) -> None:
        """The positive half of the occupancy comparison: only the CLAIMED path matters."""
        snapshot = self.read("snapshot")
        root = snapshot["repository"]["worktree_path"]
        snapshot["worktrees"] = sorted(
            [
                *snapshot["worktrees"],
                {"branch": "other", "head": "a" * 40, "path": f"{root}/.worktrees/something-else"},
            ],
            key=lambda entry: entry["path"],
        )
        code, result, _ = self.mutate_and_admit("snapshot", snapshot, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_node_claiming_a_path_outside_the_repository_is_an_inadmissible_plan(self) -> None:
        """An absolute or climbing custody path could not be located inside the observed tree, so its
        occupancy could never be compared; that is a refusal, not an unchecked pass."""
        for value, fragment in (
            ("/tmp/somewhere", "absolute rather than repository-relative"),
            ("../outside/worktree", "climbs out of the repository"),
            (".worktrees//doubled", "different custody"),
            (".worktrees\\windows", "forward-slashed"),
            ("", "neither null nor a non-empty string"),
        ):
            with self.subTest(custody=value):
                self.setUp()
                document = put(self.read("plan"), "nodes.1.worktree_custody", value)
                code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, "wave-plan", fragment)

    def test_an_unknown_worktrees_dimension_refuses_the_honestly_incomplete_occupancy_list(self) -> None:
        """A `worktrees` (or `worktrees.branch`) unknown is not an empty occupancy list; it is no
        observation of one, and this check must not read the two the same way."""
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)  # positive control: the identical snapshot minus the unknown admits
        for dimension in ("worktrees", "worktrees.branch"):
            with self.subTest(dimension=dimension):
                self.setUp()
                snapshot = self.read("snapshot")
                snapshot["unknowns"] = sorted(
                    [*snapshot["unknowns"], {"dimension": dimension, "reason": "not observed for this test"}],
                    key=lambda entry: entry["dimension"],
                )
                code, result, _ = self.mutate_and_admit("snapshot", snapshot, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_only_blocked_check(
                    result, "dependency-and-artifact-availability", dimension, "among its own unknowns"
                )

    def test_an_unknown_dirty_state_refuses_the_honestly_incomplete_all_zero_count(self) -> None:
        """A `dirty_state` unknown is not an all-zero clean tree; it is no observation of one, and this
        check must not read the two the same way."""
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)  # positive control: the identical snapshot minus the unknown admits
        self.setUp()
        snapshot = self.read("snapshot")
        snapshot["unknowns"] = sorted(
            [*snapshot["unknowns"], {"dimension": "dirty_state", "reason": "git status could not be run"}],
            key=lambda entry: entry["dimension"],
        )
        code, result, _ = self.mutate_and_admit("snapshot", snapshot, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "dependency-and-artifact-availability", "dirty_state", "among its own unknowns"
        )


class PolicyAndBoundsTests(ToolCase):
    """The applicable policy this gate can read: the mission's ladder and the plan's own limits."""

    def rebind(self, mutation: dict[str, Any]) -> None:
        """Write a mutated mission AND repoint the plan at its new digest.

        Both, because the mission-agreement comparison runs first and stops the rest: a mission
        mutated on its own would be refused for not being the plan's contract, and the ladder
        comparison under test would never run.
        """
        mission = seal(mutation)
        self.write("mission", mission)
        self.write("plan", seal(put(self.read("plan"), "inputs.mission_digest", mission["digest"])))

    def test_the_plans_own_contract_bounds_it(self) -> None:
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_plan_compiled_against_a_different_contract_is_refused(self) -> None:
        document = put(self.read("plan"), "inputs.mission_digest", fake_digest("some other contract"))
        code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        report = self.assert_only_blocked_check(
            result,
            "policy-and-adr-consistency",
            "compiled against a different contract",
            FIXTURES["mission_digest"],
        )
        # ONE blocker: the ladder re-check is deliberately not attempted against the wrong contract.
        groups = {entry["slug"]: entry for entry in report["checks"]}
        self.assertEqual(len(groups["policy-and-adr-consistency"]["blockers"]), 1)

    def test_two_documents_naming_two_missions_cannot_bound_each_other(self) -> None:
        self.rebind(put(self.read("mission"), "mission_id", "mission-somewhere-else"))
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "policy-and-adr-consistency", MISSION_ID, "mission-somewhere-else", "cannot bound each other"
        )

    def test_a_node_carrying_an_unadmitted_authority_class_is_refused(self) -> None:
        document = put(self.read("plan"), "nodes.1.authority_class", "authorized-fan-in")
        code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "policy-and-adr-consistency", "ws-b-admission", "does not admit", "mission revision"
        )

    def test_a_node_above_the_missions_ceiling_is_refused(self) -> None:
        """Admitted and still too high: the ladder is ordered, so `ceiling` bounds it a second time."""
        self.rebind(
            put(
                self.read("mission"),
                "authority",
                {
                    "admitted_classes": ["read-only-advisory", "owned-worktree-write", "authorized-fan-in"],
                    "ceiling": "owned-worktree-write",
                },
            )
        )
        self.write("plan", seal(put(self.read("plan"), "nodes.1.authority_class", "authorized-fan-in")))
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "policy-and-adr-consistency", "above the", "ceiling 'owned-worktree-write'"
        )

    def test_a_ladder_that_is_not_a_leading_prefix_is_an_inadmissible_contract(self) -> None:
        self.rebind(
            put(
                self.read("mission"),
                "authority",
                {"admitted_classes": ["read-only-advisory", "authorized-fan-in"], "ceiling": "authorized-fan-in"},
            )
        )
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "mission-contract", "leading prefix", "ordered ladder")

    def test_more_nodes_than_the_recorded_execution_profile_allows_is_refused(self) -> None:
        document = put(self.read("plan"), "limits.max_total_nodes", 1)
        code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "policy-and-adr-consistency", "carries 2 nodes against the execution-profile ceiling of 1"
        )

    def test_more_concurrency_than_the_recorded_execution_profile_allows_is_refused(self) -> None:
        document = put(self.read("plan"), "limits.max_concurrent_nodes", 1)
        code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "policy-and-adr-consistency",
            "declares 2 concurrent nodes against the execution-profile ceiling of 1",
        )

    def test_limits_that_are_not_three_positive_ceilings_are_an_inadmissible_plan(self) -> None:
        for dotted, value, fragment in (
            ("limits.max_total_nodes", 0, "at least 1"),
            ("limits.max_concurrent_nodes", -2, "at least 0"),
            ("limits.recursive_spawn_generations", -1, "at least 0"),
            ("limits.max_total_nodes", "many", "at least 0"),
        ):
            with self.subTest(field=dotted, value=value):
                self.setUp()
                document = put(self.read("plan"), dotted, value)
                code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused_input(result, "wave-plan", dotted, fragment)

    def test_a_recursion_generation_count_of_zero_is_admitted_because_zero_means_off(self) -> None:
        """The positive half of the floor above: 0 is the honest record of recursion being off."""
        document = put(self.read("plan"), "limits.recursive_spawn_generations", 0)
        code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)


class HostCapabilityTests(ToolCase):
    """Demands re-checked against the FRESH observation, which is where drift actually shows up."""

    def test_the_observed_host_satisfies_the_plans_demands(self) -> None:
        snapshot = self.read("snapshot")
        self.assertIsNotNone(snapshot["host_capabilities"]["git"])
        self.assertIsNotNone(snapshot["host_capabilities"]["python"])
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_capability_that_is_gone_from_the_fresh_observation_refuses(self) -> None:
        """Present at compile time and absent now is exactly the drift admission exists to catch."""
        document = put(self.read("snapshot"), "host_capabilities.git", None)
        code, result, _ = self.mutate_and_admit("snapshot", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "host-and-tool-capability",
            "ws-b-admission",
            "git-worktree-write",
            "observed no host_capabilities.git",
        )

    def test_a_capability_the_snapshot_names_among_its_unknowns_refuses(self) -> None:
        """An unobserved capability is not an available one, which is a different fact from absence."""
        snapshot = self.read("snapshot")
        snapshot["unknowns"] = sorted(
            [
                *snapshot["unknowns"],
                {"dimension": "host_capabilities.python", "reason": "the interpreter could not be probed"},
            ],
            key=lambda entry: entry["dimension"],
        )
        code, result, _ = self.mutate_and_admit("snapshot", snapshot, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "host-and-tool-capability", "python-execution", "among its own unknowns"
        )

    def test_a_demand_no_snapshot_field_reports_is_deferred_by_name_rather_than_passed(self) -> None:
        """The four harness demands are unobservable, so the report NAMES that gap instead of claiming
        the demand feasible; the check is met for what it could compare and the deferral says the rest."""
        document = put(self.read("plan"), "nodes.1.capability_demands", ["subagent-dispatch"])
        code, result, _ = self.mutate_and_admit("plan", document, reseal=True)
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        deferred = {entry["dimension"]: entry["reason"] for entry in report["deferred_dimensions"]}
        self.assertIn("host-and-tool-capability:harness-demands", deferred)
        self.assertIn("subagent-dispatch", deferred["host-and-tool-capability:harness-demands"])


class UnresolvedPriorEffectTests(ToolCase):
    """No second wave over an unresolved first, bounded to what `wave_artifacts` records."""

    def artifact_path(self) -> str:
        recorded = self.read("artifact")["wave_artifacts"]
        self.assertEqual(len(recorded), 1, recorded)
        return recorded[0]["path"]

    def test_a_repository_recording_no_wave_artifact_has_no_prior_effect_to_resolve(self) -> None:
        self.assertEqual(self.read("snapshot")["wave_artifacts"], [])
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)

    def test_a_real_wave_artifact_nobody_classified_refuses_as_unclassified(self) -> None:
        code, result, _ = self.admit(fresh="artifact.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "unresolved-prior-effect",
            self.artifact_path(),
            "no schema in this family records whether a wave artifact is resolved",
        )

    def test_declaring_that_artifact_active_refuses_by_naming_it(self) -> None:
        """`--active-artifacts` sharpens the reason; it never relaxes the rule."""
        path = self.artifact_path()
        code, result, _ = self.admit("--active-artifacts", path, fresh="artifact.json")
        self.assertEqual(code, EXIT_OK)
        report = self.assert_only_blocked_check(
            result, "unresolved-prior-effect", path, "no second wave is admitted over it"
        )
        groups = {entry["slug"]: entry for entry in report["checks"]}
        blockers = groups["unresolved-prior-effect"]["blockers"]
        # ONE blocker: a classified artifact is not also unclassified.
        self.assertEqual(len(blockers), 1, blockers)
        self.assertNotIn("unclassified", blockers[0])

    def test_declaring_an_artifact_the_snapshot_does_not_record_is_a_disagreement(self) -> None:
        code, result, _ = self.admit("--active-artifacts", ".sdlc/a-wave-nobody-observed.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "unresolved-prior-effect",
            ".sdlc/a-wave-nobody-observed.json",
            "records no such wave artifact",
            "disagree about what is on disk",
        )

    def test_two_orders_of_one_declaration_seal_the_same_bytes(self) -> None:
        """The declaration is a SET, so the blockers are sorted: argv order must not move the digest."""
        one, two = ".sdlc/first.json", ".sdlc/second.json"
        code, first, _ = self.admit("--active-artifacts", one, "--active-artifacts", two)
        self.assertEqual(code, EXIT_OK)
        code, second, _ = self.admit("--active-artifacts", two, "--active-artifacts", one)
        self.assertEqual(code, EXIT_OK)
        report = self.assert_only_blocked_check(first, "unresolved-prior-effect", one, two)
        self.assertEqual(len(report["checks"][5]["blockers"]), 2)
        self.assertEqual(canonical(first["report"]), canonical(second["report"]))

    def test_an_unusable_active_artifacts_declaration_is_exit_two(self) -> None:
        for argv, fragment in (
            (["--active-artifacts", ""], "empty value"),
            (["--active-artifacts", ".sdlc/one.json", "--active-artifacts", ".sdlc/one.json"], "more than once"),
        ):
            with self.subTest(argv=argv):
                code, result, stderr = self.admit(*argv)
                self.assertEqual(code, EXIT_INPUT)
                self.assertIsNone(result, "an unusable argument must publish no result document")
                self.assertIn("--active-artifacts", stderr)
                self.assertIn(fragment, stderr)

    def test_an_unknown_wave_artifacts_refuses_the_honestly_incomplete_empty_list(self) -> None:
        """A `wave_artifacts` unknown is not an empty list; it is no observation of one, and this check
        must not read the two the same way -- an honest 'I could not observe wave_artifacts' would
        otherwise clear the one check that exists to catch an unresolved prior wave."""
        self.assertEqual(self.read("snapshot")["wave_artifacts"], [])
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)  # positive control: the identical snapshot minus the unknown admits
        self.setUp()
        snapshot = self.read("snapshot")
        snapshot["unknowns"] = sorted(
            [
                *snapshot["unknowns"],
                {"dimension": "wave_artifacts", "reason": "the .sdlc directory could not be listed"},
            ],
            key=lambda entry: entry["dimension"],
        )
        code, result, _ = self.mutate_and_admit("snapshot", snapshot, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result, "unresolved-prior-effect", "wave_artifacts", "among its own unknowns"
        )

    def test_a_wave_artifacts_detail_refinement_among_unknowns_also_refuses(self) -> None:
        """The sibling's own per-path spelling for one unreadable artifact refuses the same way as the
        whole-dimension name: a partial listing is not a complete one either."""
        snapshot = self.read("snapshot")
        snapshot["unknowns"] = sorted(
            [
                *snapshot["unknowns"],
                {
                    "dimension": "wave_artifacts:.sdlc/wave-journal.json",
                    "reason": "wave-journal.json cannot be read",
                },
            ],
            key=lambda entry: entry["dimension"],
        )
        code, result, _ = self.mutate_and_admit("snapshot", snapshot, reseal=True)
        self.assertEqual(code, EXIT_OK)
        self.assert_only_blocked_check(
            result,
            "unresolved-prior-effect",
            "wave_artifacts:<path> refinement of it",
            "among its own unknowns",
        )


class UnusableInputTests(ToolCase):
    """Exit 2: the QUESTION could not be asked. Nothing is printed to stdout, so nothing was answered."""

    def assert_exit_two(self, code: int, result: Any, stderr: str, *fragments: str) -> None:
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result, "an unusable input must publish no result document")
        for fragment in fragments:
            self.assertIn(fragment, stderr)

    def test_a_missing_file_cannot_be_read(self) -> None:
        code, result, stderr = self.invoke(
            "admit", "--plan", "absent.json", "--fresh-snapshot", "snapshot.json",
            "--mission", "mission.json", "--at", AT,
        )
        self.assert_exit_two(code, result, stderr, "cannot read the wave plan", "absent.json")

    def test_a_directory_is_not_a_regular_file(self) -> None:
        (self.work / "adirectory.json").mkdir()
        code, result, stderr = self.invoke(
            "admit", "--plan", "adirectory.json", "--fresh-snapshot", "snapshot.json",
            "--mission", "mission.json", "--at", AT,
        )
        self.assert_exit_two(code, result, stderr, "is not a regular file")

    def test_bytes_that_are_not_json_cannot_be_read(self) -> None:
        (self.work / "plan.json").write_bytes(b"{not json at all")
        code, result, stderr = self.admit()
        self.assert_exit_two(code, result, stderr, "is not JSON")

    def test_a_json_array_is_not_a_json_object(self) -> None:
        (self.work / "snapshot.json").write_bytes(b"[]\n")
        code, result, stderr = self.admit()
        self.assert_exit_two(code, result, stderr, "is not a JSON object")

    def test_a_repeated_json_key_has_two_meanings(self) -> None:
        """`json.loads` would keep the last value, which is a document with two meanings and one digest."""
        (self.work / "plan.json").write_bytes(b'{"schema":"a","schema":"b"}\n')
        code, result, stderr = self.admit()
        self.assert_exit_two(code, result, stderr, "repeats the JSON key", "'schema'")

    def test_an_unreadable_file_is_not_a_refusal(self) -> None:
        if os.geteuid() == 0:
            self.skipTest(ROOT_FS)
        target = self.work / "plan.json"
        target.chmod(0o000)
        self.addCleanup(target.chmod, stat.S_IRUSR | stat.S_IWUSR)
        code, result, stderr = self.admit()
        self.assert_exit_two(code, result, stderr, "cannot read the wave plan")

    def test_verify_reports_an_unreadable_report_the_same_way(self) -> None:
        code, result, stderr = self.invoke("verify", "--report", "absent.json")
        self.assert_exit_two(code, result, stderr, "cannot read the admission report")

    def test_an_expect_digest_that_no_document_could_match_is_unusable(self) -> None:
        for value in ("short", "Z" * 64, "A" * 64, "a" * 63, "a" * 65):
            with self.subTest(expect=value):
                code, result, stderr = self.invoke("verify", "--report", "plan.json", "--expect-digest", value)
                self.assert_exit_two(code, result, stderr, "--expect-digest", "64 lowercase hexadecimal")


class NonFiniteTests(ToolCase):
    """Both halves of the defence, because they are DIFFERENT code paths, each with a finite control."""

    def raw(self, name: str, text: str) -> None:
        (self.work / f"{name}.json").write_text(text, encoding="utf-8")

    def test_a_non_finite_constant_token_is_refused_at_a_nested_position(self) -> None:
        """`parse_constant` sees these three spellings and nothing else."""
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                self.setUp()
                document = json.dumps(self.read("plan"))
                # Nested inside the head object rather than at the top level, so the refusal cannot be
                # attributed to a shallow scan of the document's own keys.
                spliced = document.replace('"head": {', '"head": {"drift": ' + token + ", ", 1)
                if spliced == document:  # canonical output has no spaces after the colon
                    spliced = document.replace('"head":{', '"head":{"drift":' + token + ",", 1)
                self.raw("plan", spliced)
                code, result, stderr = self.admit()
                self.assertEqual(code, EXIT_INPUT)
                self.assertIsNone(result)
                self.assertIn("non-finite JSON constant", stderr)
                self.assertIn(token, stderr)

    def test_an_overflowing_literal_inside_a_list_is_refused_by_the_post_parse_walk(self) -> None:
        """`1e400` never reaches `parse_constant`: it is an ordinary number that overflows to inf."""
        plan = self.read("plan")
        plan["nodes"][0]["dependencies"].append(OVERFLOW)
        self.raw("plan", overflowing(plan))
        code, result, stderr = self.admit()
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("non-finite number", stderr)
        self.assertIn("at position", stderr)

    def test_a_finite_number_at_the_same_list_position_is_not_an_exit_two(self) -> None:
        """The positive control for the case above: the exit 2 came from the overflow, not the mutation."""
        plan = self.read("plan")
        plan["nodes"][0]["dependencies"].append(1e40)
        self.raw("plan", json.dumps(plan))
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        # Refused for a SHAPE reason -- the stale digest -- which is exactly not exit 2.
        self.assert_refused_input(result, "wave-plan", "does not re-derive")

    def test_an_overflowing_literal_deep_inside_nested_objects_is_refused(self) -> None:
        snapshot = self.read("snapshot")
        snapshot["dirty_state"]["staged"] = [{"level": {"deeper": [OVERFLOW]}}]
        self.raw("snapshot", overflowing(snapshot))
        code, result, stderr = self.admit()
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("non-finite number", stderr)
        self.assertIn("at key", stderr)

    def test_a_finite_number_at_the_same_nested_position_is_not_an_exit_two(self) -> None:
        snapshot = self.read("snapshot")
        snapshot["dirty_state"]["staged"] = [{"level": {"deeper": [1e40]}}]
        self.write("snapshot", seal(snapshot))
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        # A named refusal of the SHAPE -- `dirty_state.staged` is a count, and the custody check reads
        # it -- which is exactly not exit 2, and that is what makes the exit 2 above attributable to
        # the overflow rather than to the mutation.
        self.assert_refused_input(result, "planning-snapshot", "dirty_state.staged", "integer of at least 0")

    def test_a_non_finite_constant_is_refused_in_every_input_position(self) -> None:
        for name in ("plan", "snapshot", "mission"):
            with self.subTest(input=name):
                self.setUp()
                self.raw(name, '{"schema":"x","drift":[[NaN]]}')
                code, result, stderr = self.admit()
                self.assertEqual(code, EXIT_INPUT)
                self.assertIsNone(result)
                self.assertIn("non-finite JSON constant", stderr)

    def test_verify_refuses_a_non_finite_report_the_same_way(self) -> None:
        self.raw("report", '{"schema":"agentic-sdlc/wave-plan-admission@1","plan_revision":Infinity}')
        code, result, stderr = self.invoke("verify", "--report", "report.json")
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("non-finite JSON constant", stderr)


def report_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid `wave-plan-admission@1` body: the control every negative case starts from.

    Hand-built rather than captured, and sealed with this module's own derivation, so `verify` is
    proved to agree with the family's published contract rather than with the tool that wrote it.
    """
    body: dict[str, Any] = {
        "schema": ADMISSION_SCHEMA,
        "admitted_at": AT,
        "checks": [{"blockers": [], "met": True, "slug": "snapshot-freshness"}],
        "deferred_dimensions": [
            {"dimension": "approval-requirements", "reason": "no approval receipt is an input to this gate"},
            {"dimension": "budgets-and-declared-egress", "reason": "no merged schema carries a budget"},
        ],
        "disposition": ADMITTED,
        "inputs": {
            "mission_digest": fake_digest("mission"),
            "plan_digest": fake_digest("plan"),
            "snapshot_digest": fake_digest("snapshot"),
        },
        "mission_id": MISSION_ID,
        "observed": {
            "head": {"branch": "trunk", "commit_sha": "a" * 40, "tree_sha": "b" * 40},
            "snapshot_stated_at": "2026-08-19T03:30:00Z",
        },
        "plan_revision": 1,
    }
    body.update(overrides)
    return body


class ReportShapeTests(ToolCase):
    """`verify` against hand-sealed reports: the closed shape, and the one derived cross-check."""

    needs_git = False

    def verify(self, body: dict[str, Any], *extra: str, reseal: bool = True) -> Any:
        document = seal(body) if reseal else body
        self.write("report", document)
        return self.invoke("verify", "--report", "report.json", *extra)

    def assert_verified(self, result: dict[str, Any], body: dict[str, Any]) -> None:
        """The POSITIVE CONTROL: no reason at all, and the checked document republished."""
        self.assertEqual(result["verdict"], VERIFIED)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["command"], "verify")
        self.assertIsNone(result["inputs_admitted"])
        self.assertIsNone(result["out"])
        self.assertEqual(result["report"], seal(body))
        self.assertEqual(result["report_digest"], expected_digest(seal(body)))
        self.assertEqual(
            [entry["slug"] for entry in result["checks"]],
            ["closed-key-set", "admission-report-shape", "digest"],
        )

    def assert_report_refused(self, result: dict[str, Any], slug: str, *fragments: str) -> None:
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIsNone(result["report"], "a refusal must publish no report a consumer could bind")
        self.assertIsNone(result["report_digest"])
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn(slug, groups)
        self.assertFalse(groups[slug]["met"])
        joined = " ".join(groups[slug]["reasons"])
        for fragment in fragments:
            self.assertIn(fragment, joined)

    def test_the_hand_sealed_control_verifies(self) -> None:
        body = report_body()
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_expect_digest_binds_the_derived_value(self) -> None:
        body = report_body()
        code, result, _ = self.verify(body, "--expect-digest", expected_digest(seal(body)))
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_a_wrong_expect_digest_is_refused(self) -> None:
        body = report_body()
        code, result, _ = self.verify(body, "--expect-digest", fake_digest("some other report"))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "digest", "--expect-digest", "is not this report's content digest")

    def test_an_edited_report_no_longer_re_derives_its_digest(self) -> None:
        sealed = seal(report_body())
        sealed["plan_revision"] = 2
        code, result, _ = self.verify(sealed, reseal=False)
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "digest", "does not re-derive")

    def test_a_digest_that_a_convenient_writer_chose_cannot_satisfy_expect_digest(self) -> None:
        """`--expect-digest` is compared against the DERIVED value, never the recorded one."""
        sealed = seal(report_body())
        forged = fake_digest("a digest the writer preferred")
        sealed["digest"] = forged
        code, result, _ = self.verify(sealed, "--expect-digest", forged, reseal=False)
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "digest", "does not re-derive", "--expect-digest")

    def test_a_document_of_another_kind_is_not_an_admission_report(self) -> None:
        code, result, _ = self.verify(report_body(schema=PLAN_SCHEMA))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "closed-key-set", PLAN_SCHEMA, "is not an admission report")

    def test_an_unrecognised_or_missing_report_key_is_refused(self) -> None:
        code, result, _ = self.verify(report_body(surprise="a field this schema does not carry"))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "closed-key-set", "closed sealed key set", "'surprise'")

        self.setUp()
        code, result, _ = self.verify(drop(report_body(), "observed"))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "closed-key-set", "closed sealed key set", "'observed'")

    def test_a_disposition_outside_the_closed_vocabulary_is_refused(self) -> None:
        code, result, _ = self.verify(report_body(disposition="probably-fine"))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "closed vocabulary", "probably-fine")

    def test_a_disposition_its_own_checks_do_not_derive_is_refused(self) -> None:
        """The one cross-check that makes the disposition non-decorative, in both directions."""
        unmet = [
            {"blockers": ["the recorded head is not the current head"], "met": False, "slug": "snapshot-freshness"}
        ]
        code, result, _ = self.verify(report_body(disposition=ADMITTED, checks=unmet))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "derive 'blocked'", "1 unmet")

        self.setUp()
        code, result, _ = self.verify(report_body(disposition=BLOCKED))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "derive 'admitted'", "0 unmet")

    def test_a_blocked_report_that_names_its_blockers_verifies(self) -> None:
        """The positive half of the cross-check: `blocked` is an ANSWER, and it is fully verifiable."""
        body = report_body(
            disposition=BLOCKED,
            checks=[
                {"blockers": [], "met": True, "slug": "host-and-tool-capability"},
                {
                    "blockers": ["the plan's recorded head is not the observed head"],
                    "met": False,
                    "slug": "snapshot-freshness",
                },
            ],
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_a_met_check_that_still_names_a_blocker_contradicts_itself(self) -> None:
        checks = [{"blockers": ["something was wrong after all"], "met": True, "slug": "snapshot-freshness"}]
        code, result, _ = self.verify(report_body(checks=checks))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "is met and still names 1 blocker")

    def test_an_unmet_check_with_no_blocker_is_the_thing_a_report_exists_to_prevent(self) -> None:
        checks = [{"blockers": [], "met": False, "slug": "snapshot-freshness"}]
        code, result, _ = self.verify(report_body(disposition=BLOCKED, checks=checks))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "unmet and names no blocker")

    def test_a_report_naming_no_check_at_all_is_refused(self) -> None:
        for value in ([], {}, None, "snapshot-freshness"):
            with self.subTest(checks=value):
                self.setUp()
                code, result, _ = self.verify(report_body(checks=value))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", "not a non-empty array")

    def test_a_repeated_check_slug_gives_one_property_two_records(self) -> None:
        checks = [
            {"blockers": [], "met": True, "slug": "snapshot-freshness"},
            {"blockers": [], "met": True, "slug": "snapshot-freshness"},
        ]
        code, result, _ = self.verify(report_body(checks=checks))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "more than once")

    def test_a_check_slug_outside_the_closed_vocabulary_is_refused(self) -> None:
        checks = [{"blockers": [], "met": True, "slug": "vibes-were-good"}]
        code, result, _ = self.verify(report_body(checks=checks))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "closed vocabulary", "vibes-were-good")

    def test_a_report_naming_all_eleven_issue_16_checks_verifies_against_this_revision(self) -> None:
        """The forward-compatibility promise, checked: a later revision's report is a `@1` report.

        The slug vocabulary is declared in full in this revision precisely so a report from the
        revision that decides all eleven still verifies here -- and its deferred list is then EMPTY,
        which is the honest record of a gate that defers nothing. Without this case that promise would
        be a comment.
        """
        body = report_body(
            disposition=ADMITTED,
            checks=[{"blockers": [], "met": True, "slug": slug} for slug in ISSUE_16_SLUGS],
            deferred_dimensions=[],
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)
        self.assertEqual(len(result["report"]["checks"]), 11)
        self.assertEqual(result["report"]["deferred_dimensions"], [])

    def test_a_met_check_that_the_same_report_defers_as_a_whole_dimension_is_refused(self) -> None:
        """The one cross-check that makes `deferred_dimensions` load-bearing rather than prose.

        Met means a comparison ran and passed; deferred means there was none to run. A report claiming
        both about one dimension is the vacuous pass the deferred list exists to prevent, and it would
        otherwise re-derive its own digest perfectly.
        """
        body = report_body(
            checks=[{"blockers": [], "met": True, "slug": "approval-requirements"}],
            deferred_dimensions=[
                {"dimension": "approval-requirements", "reason": "no approval receipt is an input here"}
            ],
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(
            result, "admission-report-shape", "'approval-requirements' met while", "cannot claim both"
        )

    def test_a_met_check_whose_report_defers_only_a_REFINEMENT_of_it_verifies(self) -> None:
        """The positive half: `<slug>:<aspect>` leaves the rest of that check decidable, so met stands."""
        body = report_body(
            checks=[{"blockers": [], "met": True, "slug": "host-and-tool-capability"}],
            deferred_dimensions=[
                {
                    "dimension": "host-and-tool-capability:version-qualification",
                    "reason": "whether an observed version qualifies for a demand is a policy judgment",
                }
            ],
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_an_unmet_check_may_be_deferred_without_contradiction(self) -> None:
        """Only MET contradicts a deferral: an unmet check with a blocker claims no proof at all."""
        body = report_body(
            disposition=BLOCKED,
            checks=[
                {"blockers": ["this dimension is not decided here"], "met": False, "slug": "approval-requirements"}
            ],
            deferred_dimensions=[{"dimension": "approval-requirements", "reason": "no approval receipt is an input"}],
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_a_deferred_dimension_outside_the_closed_vocabulary_is_refused(self) -> None:
        """An invented name would let a report excuse itself from a check nobody agreed to defer."""
        body = report_body(
            deferred_dimensions=[{"dimension": "the-hard-parts", "reason": "we would rather not"}]
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "closed vocabulary", "the-hard-parts")

    def test_every_deferred_name_the_tool_itself_emits_is_in_that_vocabulary(self) -> None:
        """The positive control for the case above, over the whole list rather than one member."""
        body = report_body(
            deferred_dimensions=[
                {"dimension": name, "reason": f"a stated reason for {name}"} for name in DEFERRED_NAMES
            ]
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_a_repeated_deferred_dimension_gives_one_absence_two_reasons(self) -> None:
        body = report_body(
            deferred_dimensions=[
                {"dimension": "approval-requirements", "reason": "one reason"},
                {"dimension": "approval-requirements", "reason": "another reason"},
            ]
        )
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "more than once", "approval-requirements")

    def test_a_deferred_entry_that_is_not_the_closed_key_set_or_a_stated_reason_is_refused(self) -> None:
        for deferred, fragment in (
            ([{"dimension": "approval-requirements"}], "closed key set"),
            ([{"dimension": "approval-requirements", "reason": "why", "extra": 1}], "closed key set"),
            ([["approval-requirements", "why"]], "not a JSON object"),
            ([{"dimension": "approval-requirements", "reason": ""}], "not a non-empty string"),
            ("approval-requirements", "not an array"),
        ):
            with self.subTest(fragment=fragment):
                self.setUp()
                code, result, _ = self.verify(report_body(deferred_dimensions=deferred))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", fragment)

    def test_a_check_entry_that_is_not_the_closed_key_set_is_refused(self) -> None:
        for checks in (
            [{"met": True, "slug": "snapshot-freshness"}],
            [{"blockers": [], "met": True, "slug": "snapshot-freshness", "note": "extra"}],
            [["snapshot-freshness", True]],
        ):
            with self.subTest(checks=checks):
                self.setUp()
                code, result, _ = self.verify(report_body(checks=checks))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", "checks[0]")

    def test_a_met_flag_that_is_not_a_boolean_is_refused(self) -> None:
        for value in ("true", 1, None):
            with self.subTest(met=value):
                self.setUp()
                checks = [{"blockers": [], "met": value, "slug": "snapshot-freshness"}]
                code, result, _ = self.verify(report_body(checks=checks))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", "met is not a boolean")

    def test_blockers_that_are_not_non_empty_strings_are_refused(self) -> None:
        for value in ("one blocker", [""], [None], {}):
            with self.subTest(blockers=value):
                self.setUp()
                checks = [{"blockers": value, "met": False, "slug": "snapshot-freshness"}]
                code, result, _ = self.verify(report_body(disposition=BLOCKED, checks=checks))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", "array of non-empty strings")

    def test_a_malformed_instant_is_refused_in_both_of_its_positions(self) -> None:
        for dotted in ("admitted_at", "observed.snapshot_stated_at"):
            with self.subTest(field=dotted):
                self.setUp()
                code, result, _ = self.verify(put(report_body(), dotted, "2026-08-19T05:00:00+00:00"))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(
                    result, "admission-report-shape", "YYYY-MM-DDTHH:MM:SSZ", dotted.split(".")[-1]
                )

    def test_a_malformed_object_name_or_branch_is_refused(self) -> None:
        for dotted, fragment in (
            ("observed.head.commit_sha", "git object name"),
            ("observed.head.tree_sha", "git object name"),
            ("observed.head.branch", "neither null nor a non-empty string"),
        ):
            with self.subTest(field=dotted):
                self.setUp()
                code, result, _ = self.verify(put(report_body(), dotted, "" if "branch" in dotted else "nope"))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", fragment)

    def test_a_null_branch_verifies_because_a_detached_head_is_an_observation(self) -> None:
        body = put(report_body(), "observed.head.branch", None)
        code, result, _ = self.verify(body)
        self.assertEqual(code, EXIT_OK)
        self.assert_verified(result, body)

    def test_a_nested_object_that_is_not_its_closed_key_set_is_refused(self) -> None:
        for body, fragment in (
            (drop(report_body(), "inputs.plan_digest"), "'plan_digest'"),
            (put(report_body(), "inputs.extra", fake_digest("extra")), "'extra'"),
            (drop(report_body(), "observed.head"), "'head'"),
            (put(report_body(), "observed.head.extra", "x"), "'extra'"),
        ):
            with self.subTest(fragment=fragment):
                self.setUp()
                code, result, _ = self.verify(body)
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", "closed key set", fragment)

    def test_an_input_digest_that_is_not_a_sha256_is_refused(self) -> None:
        code, result, _ = self.verify(put(report_body(), "inputs.plan_digest", "a" * 40))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "inputs.plan_digest", "64 lowercase hexadecimal")

    def test_a_plan_revision_below_one_is_refused(self) -> None:
        for value in (0, -3, True, "1"):
            with self.subTest(revision=value):
                self.setUp()
                code, result, _ = self.verify(report_body(plan_revision=value))
                self.assertEqual(code, EXIT_OK)
                self.assert_report_refused(result, "admission-report-shape", "integer of at least 1")

    def test_a_mission_id_that_is_not_an_identifier_is_refused(self) -> None:
        code, result, _ = self.verify(report_body(mission_id="../escape"))
        self.assertEqual(code, EXIT_OK)
        self.assert_report_refused(result, "admission-report-shape", "unreserved characters")


class InstantGuardTests(ToolCase):
    """`--at` is an ARGUMENT, and the guard is `[0-9]`. Both halves of that sentence are checked here."""

    needs_git = False

    def test_an_arabic_indic_instant_is_refused_and_a_backslash_d_guard_would_have_accepted_it(self) -> None:
        arabic = "\u0662\u0660\u0662\u0666-\u0660\u0668-\u0661\u0669T\u0660\u0665:\u0660\u0660:\u0660\u0660Z"
        # The positive control for the character class: `\d` matches every Unicode decimal digit, so a
        # `\d`-based guard really would accept this string. Without this assertion the case below could
        # decay into "some malformed string is refused", which is a different and weaker claim.
        self.assertIsNotNone(re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z", arabic))
        code, result, stderr = self.admit(at=arabic)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("--at", stderr)
        self.assertIn("YYYY-MM-DDTHH:MM:SSZ", stderr)

    def test_every_other_instant_shape_is_refused(self) -> None:
        for value in (
            "2026-08-19T05:00:00",
            "2026-08-19 05:00:00Z",
            "2026-08-19T05:00:00+00:00",
            "2026-08-19T05:00:00.000Z",
            "20260819T050000Z",
            "2026-8-19T05:00:00Z",
            "12026-08-19T05:00:00Z",
            "",
            " 2026-08-19T05:00:00Z",
            "2026-08-19T05:00:00Z ",
        ):
            with self.subTest(at=value):
                code, result, stderr = self.admit(at=value)
                self.assertEqual(code, EXIT_INPUT)
                self.assertIsNone(result)
                self.assertIn("--at", stderr)

    def test_the_guard_runs_before_any_file_is_read(self) -> None:
        """This tool reads no clock, so a malformed instant has nothing to fall back to -- and it must
        be refused as the ARGUMENT it is rather than after a file error masks it."""
        code, result, stderr = self.invoke(
            "admit", "--plan", "absent-plan.json", "--fresh-snapshot", "absent-snapshot.json",
            "--mission", "absent-mission.json", "--at", "yesterday",
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("--at", stderr)
        self.assertNotIn("absent-plan.json", stderr)

    def test_verify_takes_no_instant_and_a_missing_at_is_a_grammar_error(self) -> None:
        code, result, stderr = self.invoke("verify", "--report", "report.json", "--at", AT)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("unrecognized arguments", stderr)

        code, result, stderr = self.invoke(
            "admit", "--plan", "plan.json", "--fresh-snapshot", "snapshot.json", "--mission", "mission.json"
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertIsNone(result)
        self.assertIn("--at", stderr)


class OutputPathTests(ToolCase):
    """The whole `--out` contract: what lands, what is refused, and what is left behind."""

    def test_the_written_file_is_the_canonical_sealed_report_and_nothing_else(self) -> None:
        code, result, _ = self.admit(out="report.json")
        self.assertEqual(code, EXIT_OK)
        report = self.assert_admitted(result)
        target = self.work / "report.json"
        self.assertEqual(result["out"], str(target))
        self.assertEqual(target.read_bytes(), canonical(report))
        self.assertTrue(target.read_bytes().endswith(b"}\n"))

    def test_the_written_report_verifies_and_binds_the_digest_the_result_published(self) -> None:
        """The round trip a consumer actually performs: admit, then verify the file it was handed."""
        code, result, _ = self.admit(out="report.json")
        self.assertEqual(code, EXIT_OK)
        digest = result["report_digest"]
        code, verified, _ = self.invoke("verify", "--report", "report.json", "--expect-digest", digest)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(verified["reasons"], [])
        self.assertEqual(verified["report"], result["report"])
        self.assertEqual(verified["report_digest"], digest)

    def test_a_blocked_report_is_written_and_verifies_exactly_like_an_admitted_one(self) -> None:
        """Issue 16 line 130's "or exact blockers": a completed admission whose answer is no is still
        the durable, digest-bound evidence a caller who must not dispatch has to keep."""
        code, result, _ = self.admit(fresh="moved.json", out="blocked.json")
        self.assertEqual(code, EXIT_OK)
        report = self.assert_blocked(result, "snapshot-freshness", "the target moved")
        self.assertEqual((self.work / "blocked.json").read_bytes(), canonical(report))
        code, verified, _ = self.invoke(
            "verify", "--report", "blocked.json", "--expect-digest", result["report_digest"]
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(verified["reasons"], [])
        self.assertEqual(verified["report"]["disposition"], BLOCKED)

    def test_no_out_creates_nothing(self) -> None:
        before = sorted(entry.name for entry in self.work.iterdir())
        code, result, _ = self.admit()
        self.assertEqual(code, EXIT_OK)
        self.assert_admitted(result)
        self.assertIsNone(result["out"])
        self.assertEqual(sorted(entry.name for entry in self.work.iterdir()), before)

    def test_an_occupied_destination_is_refused_rather_than_replaced(self) -> None:
        target = self.work / "report.json"
        target.write_bytes(b"an earlier run's evidence\n")
        code, result, _ = self.admit(out="report.json")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIsNone(result["report"])
        self.assertIsNone(result["out"])
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn("already exists", " ".join(groups["output-path"]["reasons"]))
        self.assertEqual(target.read_bytes(), b"an earlier run's evidence\n")

    def test_a_destination_with_no_existing_parent_is_refused(self) -> None:
        code, result, _ = self.admit(out="no/such/directory/report.json")
        self.assertEqual(code, EXIT_OK)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn("nowhere to land", " ".join(groups["output-path"]["reasons"]))
        self.assertIsNone(result["report"])

    def test_a_destination_inside_the_observed_repository_is_refused(self) -> None:
        """Writing a report into the tree it admits would make the snapshot's own dirty state wrong."""
        repository = FIXTURES["repository"]
        for out, key in (
            (repository / "report.json", "worktree_path"),
            (repository / "nested" / "report.json", "worktree_path"),
            (repository / ".git" / "report.json", "git_dir"),
        ):
            with self.subTest(out=str(out)):
                self.setUp()
                out.parent.mkdir(parents=True, exist_ok=True)
                code, result, _ = self.admit(out=str(out))
                self.assertEqual(code, EXIT_OK)
                groups = {entry["slug"]: entry for entry in result["checks"]}
                joined = " ".join(groups["output-path"]["reasons"])
                self.assertIn("resolves inside the snapshot's observed", joined)
                self.assertIn(key, joined)
                self.assertIsNone(result["report"])
                self.assertFalse(out.exists())

    def test_containment_is_measured_through_a_symlinked_parent(self) -> None:
        """Lexical containment would be defeated by a link, so both sides are resolved."""
        link = self.work / "elsewhere"
        try:
            link.symlink_to(FIXTURES["repository"], target_is_directory=True)
        except OSError:  # a host without symlink permission cannot ask this question
            self.skipTest("this host does not permit creating a symlink")
        code, result, _ = self.admit(out="elsewhere/report.json")
        self.assertEqual(code, EXIT_OK)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn("resolves inside the snapshot's observed", " ".join(groups["output-path"]["reasons"]))
        self.assertIsNone(result["report"])
        self.assertFalse((FIXTURES["repository"] / "report.json").exists())

    def test_an_inadmissible_input_writes_no_file(self) -> None:
        self.write("plan", seal(put(self.read("plan"), "schema", "agentic-sdlc/wrong@1")))
        code, result, _ = self.admit(out="report.json")
        self.assertEqual(code, EXIT_OK)
        self.assert_refused_input(result, "wave-plan", "agentic-sdlc/wrong@1")
        self.assertFalse((self.work / "report.json").exists())

    def test_containment_is_not_measured_against_a_refused_snapshot(self) -> None:
        """A destination inside the observed tree is refused ONCE, by the input that was admitted.

        With the snapshot itself inadmissible there is no observed repository to compare against, so
        the output-path group stays silent rather than claiming a containment it could not measure.
        """
        self.write("snapshot", seal(put(self.read("snapshot"), "schema", "agentic-sdlc/wrong@1")))
        code, result, _ = self.admit(out=str(FIXTURES["repository"] / "report.json"))
        self.assertEqual(code, EXIT_OK)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertTrue(groups["output-path"]["met"])
        self.assertFalse(groups["planning-snapshot"]["met"])
        self.assertIsNone(result["report"])
        self.assertFalse((FIXTURES["repository"] / "report.json").exists())

    def test_a_destination_that_cannot_be_created_is_an_internal_failure_with_the_report_delivered(self) -> None:
        """The file is the convenience; the result document is the evidence, so it still arrives."""
        if os.geteuid() == 0:
            self.skipTest(ROOT_FS)
        sealed_off = self.work / "sealed-off"
        sealed_off.mkdir()
        sealed_off.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(sealed_off.chmod, stat.S_IRWXU)
        code, result, stderr = self.admit(out="sealed-off/report.json")
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn("cannot create the --out path", stderr)
        self.assertIn("nothing was written", stderr)
        report = self.assert_admitted(result)
        self.assertIsNotNone(report)
        self.assertIsNone(result["out"])
        self.assertEqual(result["exit_code"], EXIT_INTERNAL)
        self.assertEqual(list(sealed_off.iterdir()), [])

    def test_the_result_exit_code_field_agrees_with_the_process_exit_code(self) -> None:
        code, result, _ = self.admit(out="report.json")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["exit_code"], code)


class WriteDocumentRaceGuardTests(unittest.TestCase):
    """`write_document`'s own `O_EXCL`, isolated from `check_output_path`'s earlier existence check.

    `admit`'s CLI path always refuses an occupied `--out` before `write_document` is ever reached, so a
    subprocess-level test can never exercise `O_EXCL` losing a race to a file that appeared in between:
    it would only ever prove the earlier check. This class imports the tool directly -- its hyphenated
    filename means a plain `import` statement cannot name it, so `importlib.util.spec_from_file_location`
    loads it under a module name of this test's choosing -- and calls `write_document` against a target
    that already exists, which is exactly what a racer winning that gap would leave behind.
    """

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("wave_plan_admission_race_guard", TOOL)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name).resolve()

    def test_a_pre_existing_target_is_left_untouched_and_reports_nothing_created(self) -> None:
        target = self.work / "report.json"
        target.write_bytes(b"a racer's file, already here\n")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            state = self.module.write_document(target, {"schema": "agentic-sdlc/wave-plan-admission@1"})
        self.assertEqual(state, self.module.WRITE_NOTHING)
        self.assertEqual(target.read_bytes(), b"a racer's file, already here\n")
        self.assertIn("cannot create the --out path", captured.getvalue())
        self.assertIn("nothing was written", captured.getvalue())


class DeterminismTests(ToolCase):
    """Identical inputs seal identical BYTES, whatever the child's hash seed or process directory."""

    def sealed_report(self, *, extra: dict[str, str] | None = None, cwd: Path | None = None) -> bytes:
        code, result, _ = self.invoke(
            "admit",
            "--plan", str(self.work / "plan.json"),
            "--fresh-snapshot", str(self.work / "snapshot.json"),
            "--mission", str(self.work / "mission.json"),
            "--compiled-snapshot", str(self.work / "compiled.json"),
            "--at", AT,
            extra=extra,
            cwd=cwd,
        )
        self.assertEqual(code, EXIT_OK)
        return canonical(self.assert_admitted(result))

    def test_two_hash_seeds_seal_the_same_bytes(self) -> None:
        probe = [
            run(
                [sys.executable, "-B", "-c", 'print(hash("agentic-sdlc"))'],
                cwd=self.work,
                extra={"PYTHONHASHSEED": seed},
            )
            for seed in ("1", "2")
        ]
        # The positive control: comparing two runs of an interpreter whose randomization was disabled
        # would prove nothing, so the two seeds are asserted to really change string hashing first.
        self.assertNotEqual(probe[0].stdout, probe[1].stdout)
        self.assertEqual(
            self.sealed_report(extra={"PYTHONHASHSEED": "1"}),
            self.sealed_report(extra={"PYTHONHASHSEED": "2"}),
        )

    def test_the_process_directory_reaches_the_result_but_never_the_sealed_report(self) -> None:
        elsewhere = self.work / "elsewhere"
        elsewhere.mkdir()
        self.assertEqual(self.sealed_report(), self.sealed_report(cwd=elsewhere))
        # The honest other half: a RELATIVE --out is resolved against the process directory, and that
        # absolute path lands in the result document rather than in the sealed report.
        code, first, _ = self.admit(out="report.json")
        self.assertEqual(code, EXIT_OK)
        code, second, _ = self.invoke(
            "admit",
            "--plan", str(self.work / "plan.json"),
            "--fresh-snapshot", str(self.work / "snapshot.json"),
            "--mission", str(self.work / "mission.json"),
            "--compiled-snapshot", str(self.work / "compiled.json"),
            "--at", AT, "--out", "report.json",
            cwd=elsewhere,
        )
        self.assertEqual(code, EXIT_OK)
        self.assertNotEqual(first["out"], second["out"])
        self.assertEqual(first["report"], second["report"])


class AmbientInputTests(unittest.TestCase):
    """Read both files with `ast`, because a substring search cannot tell code from a docstring.

    The tool's own docstring contains the words "environment variable" and "subprocess" in the
    sentences promising it uses neither, so `grep` would report a hit for the very claim being checked.
    """

    #: Every `os` attribute the tool is allowed to touch. `environ`, `getenv`, `getcwd`, and `umask`
    #: are absent by construction: each one would make a sealed report depend on ambient state.
    ALLOWED_OS = {
        "O_CREAT",
        "O_EXCL",
        "O_WRONLY",
        "fdopen",
        "fsync",
        "open",
        "path",
    }
    #: The stdlib-only import surface. `subprocess`, `time`, `datetime`, `socket`, and `urllib` are
    #: absent by construction: this tool runs nothing, reads no clock, and opens no socket.
    ALLOWED_IMPORTS = {
        "__future__",
        "argparse",
        "collections.abc",
        "hashlib",
        "json",
        "math",
        "os",
        "pathlib",
        "re",
        "stat",
        "sys",
        "typing",
    }

    def parsed(self, path: Path) -> ast.Module:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_the_tool_touches_no_os_attribute_that_reads_ambient_state(self) -> None:
        touched = {
            node.attr
            for node in ast.walk(self.parsed(TOOL))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os"
        }
        self.assertTrue(touched, "the tool does use `os`, so an empty set means this walk found nothing")
        self.assertEqual(touched - self.ALLOWED_OS, set())

    def test_the_tool_imports_only_the_allowed_stdlib_surface(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(self.parsed(TOOL)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        self.assertTrue(imported)
        self.assertEqual(imported - self.ALLOWED_IMPORTS, set())

    def test_the_tool_imports_no_sibling_planning_tool(self) -> None:
        """Siblings are consumed as DOCUMENTS. A shared constant would hide the day the two diverged."""
        text = TOOL.read_text(encoding="utf-8")
        for name in ("mission_contract", "planning_snapshot", "wave_plan_compiler", "importlib"):
            self.assertNotIn(f"import {name}", text)

    def test_this_module_reaches_for_the_environment_only_inside_constructed_environment(self) -> None:
        module = self.parsed(Path(__file__))
        allowed = [
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "constructed_environment"
        ]
        self.assertEqual(len(allowed), 1)
        span = range(allowed[0].lineno, (allowed[0].end_lineno or allowed[0].lineno) + 1)
        reads = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr == "environ"
        ]
        self.assertTrue(reads, "this module does read os.environ, so an empty list means the walk failed")
        for node in reads:
            self.assertIn(node.lineno, span)
