"""Tests for the PlanningSnapshot capturer, its head anchor, and its digest.

Five kinds of test live here and they check different things.

The ROUND-TRIP tests capture a snapshot, then hand the sealed document straight back to `verify`, so
the two commands are proved to agree about the one digest rather than each being proved against a
constant this module chose. `verify --expect-digest` closes the loop a downstream consumer will
actually use.

The ANCHOR tests are the reason this file exists. Seed `agentic-sdlc-5ee7` is about an artifact that
names no head, so the head must be recorded AND re-read before sealing. A scripted git whose second
`rev-parse` answers differently is the only way to reach the moved-head case deterministically, which
is why almost everything here runs against a SCRIPTED git rather than the host's.

That scripted git is pinned to REAL BYTES: every fixture in `GitScript` was copied from the output of
git 2.43.0 observed while writing this module (`status --porcelain=v2 -z --untracked-files=all`,
`worktree list --porcelain -z`), so the parsers are proved against the shapes git actually emits
rather than shapes this module invented. One test class additionally builds a real repository and is
SKIPPED when git is absent; the scripted tests are the ones that must pass everywhere, so no
assertion about the tool depends on the host having git at all.

The NEGATIVE cases each carry a POSITIVE CONTROL in the same test: the unscripted-clean capture is
asserted to reach `captured` (or the unmutated sealed document `verified`) FIRST, so a test that
stopped exercising its guard would also have to stop reaching that verdict.

The CANONICAL-FORM tests assert BYTES, not parsed values, and one carries a non-ASCII branch name,
because `ensure_ascii=True` is the half of the canonical form that a JSON round-trip cannot detect.

Every spawn CONSTRUCTS its environment from an allowlist rather than inheriting the developer's, and
one test proves the tool's own child environment is constructed too: a `GIT_DIR` in the caller's
environment must not reach the git the tool runs, because an observation an ambient variable can move
is not an observation.
"""

from __future__ import annotations

import ast
import hashlib
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
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "planning-snapshot.py"

SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
RESULT_SCHEMA = "agentic-sdlc/planning-snapshot-result@1"

CAPTURED = "captured"
VERIFIED = "verified"
REFUSED = "refused"

EXIT_OK = 0
#: The undelivered-document code. A result the tool derived but could not put on stdout is neither a
#: success nor an input error, and 120 is not in the module's exit space at all.
EXIT_INTERNAL = 1
EXIT_INPUT = 2

AT = "2026-08-20T01:00:00Z"

#: Object names copied from real git output so the 40-character SHA-1 shape is the tested shape.
COMMIT_A = "18b57c521f680a24a85b3cf3ceac3b71951e510a"
COMMIT_B = "c3a187929b8f4333fbe6021e92f3f808d630f5a6"
TREE_A = "4ba58d86db85f0d57be5855696f4268e27795985"
TREE_B = "78981922613b2afb6025042ff6bd878ac1994e85"
BLOB = "c1827f07e114c20547dc6a7296588870a4b5b62c"
BRANCH_A = "work/agentic-sdlc-9359-planning-snapshot"
BRANCH_B = "main"

#: The four dimensions the tool observes in no case, so every snapshot names all four.
REQUIRED_UNKNOWNS = (
    "activation_receipts",
    "dependency_state",
    "distribution_receipt",
    "route_and_rightsizing_evidence",
)

#: Every refusal must name one of these. Nested names are included because a nested mistake must be
#: named at the level it was written, not as "the queue is wrong".
DIMENSION_NAMES = (
    "schema",
    "stated_at",
    "repository",
    "worktree_path",
    "git_dir",
    "head",
    "commit_sha",
    "tree_sha",
    "branch",
    "dirty_state",
    "worktrees",
    "queue",
    "records",
    "sha256",
    "host_capabilities",
    "policy_digests",
    "wave_artifacts",
    "unknowns",
    "digest",
    "--out",
    "--at",
    "--repository",
    "--expect-digest",
    "git",
)

#: The tool reads PATH, PATHEXT, and SYSTEMROOT and nothing else, so nothing needs scrubbing by name;
#: every spawn still CONSTRUCTS its environment from this function rather than passing `os.environ`
#: through, so a variable a future version began reading could not silently reach it from a
#: developer's shell.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every spawn in this module hands the tool: an ALLOWLIST, not an inheritance.

    Only what a usable interpreter needs is carried across. `test_a_git_control_variable_in_the_
    callers_environment_does_not_reach_git` is the assertion that a variable added here on purpose
    still cannot reach the observation.
    """
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
    has a hyphen in its name, so a plain `import` statement cannot name it, and a shared
    implementation would make this assertion vacuous.
    """
    body = {key: value for key, value in sealed.items() if key != "digest"}
    return hashlib.sha256(canonical(body)).hexdigest()


#: A scripted git/uv. It answers from a plan file beside itself and appends every invocation it saw,
#: so a test can assert both what the tool asked and what environment it asked in. A list-valued
#: answer is consumed one invocation at a time, which is how a head that MOVES between the tool's
#: first and second read is expressed.
FAKE_SOURCE = '''\
import json, os, sys
from pathlib import Path

here = Path(__file__)
plan = json.loads(here.with_suffix(".plan.json").read_text("utf-8"))
args = sys.argv[1:]
with here.with_suffix(".calls.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": args, "env": dict(os.environ), "cwd": os.getcwd()}) + "\\n")
if "--version" in args:
    key = "version"
elif "rev-parse" in args and "--show-toplevel" in args:
    key = "toplevel"
elif "rev-parse" in args and "--git-common-dir" in args:
    key = "common_dir"
elif "rev-parse" in args and any(arg.endswith("^{tree}") for arg in args):
    key = "tree"
elif "rev-parse" in args and "HEAD" in args:
    key = "head"
elif "symbolic-ref" in args:
    key = "branch"
elif "status" in args:
    key = "status"
elif "worktree" in args:
    key = "worktrees"
else:
    sys.stderr.write("scripted git: unrecognised invocation " + repr(args) + "\\n")
    raise SystemExit(97)
if key not in plan:
    sys.stderr.write("scripted git: no planned answer for " + key + "\\n")
    raise SystemExit(98)
answer = plan[key]
if isinstance(answer, list):
    counters_path = here.with_suffix(".count.json")
    try:
        counters = json.loads(counters_path.read_text("utf-8"))
    except OSError:
        counters = {}
    index = counters.get(key, 0)
    counters[key] = index + 1
    counters_path.write_text(json.dumps(counters), encoding="utf-8")
    answer = answer[min(index, len(answer) - 1)]
sys.stdout.buffer.write(answer.get("stdout", "").encode("utf-8"))
sys.stdout.buffer.flush()
raise SystemExit(answer.get("returncode", 0))
'''

#: The shebang the scripted executables carry. `sys.executable` rather than a PATH lookup, so the
#: fixtures do not depend on what the developer's PATH happens to hold, and `-SB` so twelve scripted
#: invocations per capture stay cheap.
SHEBANG = f"#!{sys.executable} -SB"


def status_record(xy: str, path: str) -> str:
    """One porcelain-v2 type-1 record, in the exact field layout git 2.43.0 emits."""
    return f"1 {xy} N... 100644 100644 100644 {TREE_B} {BLOB} {path}\0"


def unmerged_record(path: str) -> str:
    """One porcelain-v2 unmerged record: eleven fields, three stage object names."""
    return f"u UU N... 100644 100644 100644 100644 {TREE_B} {BLOB} {BLOB} {path}\0"


def worktree_entry(path: str, *, head: str | None = COMMIT_A, branch: str | None = BRANCH_A) -> str:
    """One `worktree list --porcelain -z` group, terminated by its own empty field."""
    fields = [f"worktree {path}"]
    if head is not None:
        fields.append(f"HEAD {head}")
    if branch is not None:
        fields.append(f"branch refs/heads/{branch}")
    else:
        fields.append("detached" if head is not None else "bare")
    return "".join(field + "\0" for field in fields) + "\0"


@unittest.skipUnless(len(SHEBANG) <= 127, "the interpreter path is too long for a script shebang")
class _SnapshotTestCase(unittest.TestCase):
    """One scripted repository per test: a directory with a `.git` of its own and a scripted git."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="planning-snapshot-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.root = self.work / "repo"
        (self.root / ".git").mkdir(parents=True)
        self.elsewhere = self.work / "elsewhere"
        self.elsewhere.mkdir()
        self.git = self.write_script("git", self.git_plan())
        self.uv = self.write_script("uv", {"version": {"stdout": "uv 0.11.17\n"}})

    def git_plan(self, **overrides: Any) -> dict[str, Any]:
        """A clean single-worktree repository, answered exactly as git 2.43.0 answers it."""
        plan: dict[str, Any] = {
            "version": {"stdout": "git version 2.43.0\n"},
            "toplevel": {"stdout": f"{self.root}\n"},
            "common_dir": {"stdout": ".git\n"},
            "head": {"stdout": f"{COMMIT_A}\n"},
            "tree": {"stdout": f"{TREE_A}\n"},
            "branch": {"stdout": f"{BRANCH_A}\n"},
            "status": {"stdout": ""},
            "worktrees": {"stdout": worktree_entry(str(self.root))},
        }
        plan.update(overrides)
        return plan

    def write_script(self, name: str, plan: dict[str, Any]) -> Path:
        target = self.work / f"scripted-{name}"
        target.write_text(f"{SHEBANG}\n{FAKE_SOURCE}", encoding="utf-8")
        target.chmod(0o755)
        target.with_suffix(".plan.json").write_text(json.dumps(plan), encoding="utf-8")
        return target

    def rescript_git(self, **overrides: Any) -> None:
        """Replace the scripted git's answers, discarding any sequence position already consumed."""
        self.git.with_suffix(".plan.json").write_text(json.dumps(self.git_plan(**overrides)), encoding="utf-8")
        self.git.with_suffix(".count.json").unlink(missing_ok=True)
        self.git.with_suffix(".calls.jsonl").unlink(missing_ok=True)

    def calls(self) -> list[dict[str, Any]]:
        raw = self.git.with_suffix(".calls.jsonl")
        if not raw.exists():
            return []
        return [json.loads(line) for line in raw.read_text("utf-8").splitlines() if line]

    def run_tool(self, *argv: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
        """Spawn the tool from a working directory that is NOT the observed repository."""
        return subprocess.run(
            [sys.executable, "-B", str(TOOL), *argv],
            capture_output=True,
            cwd=str(self.elsewhere),
            check=False,
            env=constructed_environment(env),
        )

    def document(self, proc: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
        """Parse stdout AND assert it is byte-exactly the canonical form of what it parsed."""
        parsed = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(proc.stdout, canonical(parsed), "stdout is not the canonical form")
        self.assertEqual(parsed["schema"], RESULT_SCHEMA, "the result document declares another schema")
        return parsed

    def capture(self, *extra: str, expect_code: int = EXIT_OK) -> dict[str, Any]:
        proc = self.run_tool(
            "capture",
            "--repository",
            str(self.root),
            "--at",
            AT,
            "--git",
            str(self.git),
            "--uv",
            str(self.uv),
            *extra,
        )
        self.assertEqual(proc.returncode, expect_code, f"capture exited {proc.returncode}: {proc.stderr!r}")
        return self.document(proc)

    def verify(self, sealed: dict[str, Any] | bytes, *extra: str, expect_code: int = EXIT_OK) -> dict[str, Any]:
        target = self.work / "supplied.json"
        target.write_bytes(sealed if isinstance(sealed, bytes) else canonical(sealed))
        proc = self.run_tool("verify", "--snapshot", str(target), *extra)
        self.assertEqual(proc.returncode, expect_code, f"verify exited {proc.returncode}: {proc.stderr!r}")
        return self.document(proc) if expect_code == EXIT_OK else {"stderr": proc.stderr.decode("utf-8")}

    def sealed(self) -> dict[str, Any]:
        result = self.capture()
        self.assertEqual(result["verdict"], CAPTURED, f"the control capture refused: {result['reasons']}")
        return result["snapshot"]

    def named(self, sealed: dict[str, Any]) -> dict[str, str]:
        return {entry["dimension"]: entry["reason"] for entry in sealed["unknowns"]}

    def reseal(self, sealed: dict[str, Any]) -> dict[str, Any]:
        """Re-derive a mutated document's digest, so a shape test is not answered by the digest."""
        body = {key: value for key, value in sealed.items() if key != "digest"}
        return {**body, "digest": expected_digest(body)}

    def assertNamesADimension(self, reasons: list[str]) -> None:
        joined = " ".join(reasons)
        self.assertTrue(
            any(name in joined for name in DIMENSION_NAMES),
            f"a refusal named no dimension a caller could act on: {reasons}",
        )


class RoundTripTests(_SnapshotTestCase):
    """Capture and verify agree about one digest, and the digest is the contract's own derivation."""

    def test_capture_seals_a_snapshot_that_verify_re_derives_and_a_consumer_can_bind(self) -> None:
        result = self.capture()
        self.assertEqual(result["verdict"], CAPTURED, result["reasons"])
        self.assertEqual(result["reasons"], [], "a captured snapshot carried reasons")
        sealed = result["snapshot"]
        self.assertEqual(sealed["schema"], SNAPSHOT_SCHEMA, "the sealed snapshot declares another schema")
        self.assertEqual(
            sealed["digest"], expected_digest(sealed), "the sealed digest is not sha256 over the canonical body"
        )
        self.assertEqual(result["digest"], sealed["digest"], "the result and the document disagree on the digest")
        verified = self.verify(sealed)
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])
        self.assertEqual(verified["digest"], sealed["digest"], "verify re-derived a different digest")
        bound = self.verify(sealed, "--expect-digest", sealed["digest"])
        self.assertEqual(bound["verdict"], VERIFIED, bound["reasons"])

    def test_verify_refuses_an_expect_digest_that_is_not_this_snapshots_digest(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed, "--expect-digest", sealed["digest"])
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        other = "0" * 64
        self.assertNotEqual(other, sealed["digest"], "the fixture digest collided with the counter-example")
        refused = self.verify(sealed, "--expect-digest", other)
        self.assertEqual(refused["verdict"], REFUSED, "a mismatched --expect-digest was accepted")
        self.assertIn(other, " ".join(refused["reasons"]), "the refusal did not name the digest that was expected")

    def test_the_same_repository_captured_from_two_working_directories_derives_one_digest(self) -> None:
        first = self.sealed()
        self.rescript_git()
        second_dir = self.work / "another-cwd"
        second_dir.mkdir()
        self.elsewhere = second_dir
        second = self.sealed()
        self.assertEqual(first["digest"], second["digest"], "the digest moved with the caller's directory")

    def test_capture_reports_the_two_checks_verify_does_not_run(self) -> None:
        captured = {entry["slug"] for entry in self.capture()["checks"]}
        self.rescript_git()
        verified = {entry["slug"] for entry in self.verify(self.sealed())["checks"]}
        self.assertIn("head-stability", captured, "capture did not report the anchor check it ran")
        self.assertIn("output-path", captured, "capture did not report the output-path check it ran")
        self.assertNotIn(
            "head-stability", verified, "verify claimed an anchor check it cannot run without re-observing"
        )
        self.assertNotIn("output-path", verified, "verify claimed an output-path check it never runs")
        self.assertIn("digest", verified, "verify did not report the digest check it ran")


class HeadAnchorTests(_SnapshotTestCase):
    """Seed agentic-sdlc-5ee7's anchor: the snapshot names the exact head, or there is no snapshot."""

    def test_the_snapshot_records_the_exact_head_the_repository_reported(self) -> None:
        sealed = self.sealed()
        self.assertEqual(
            sealed["head"],
            {"branch": BRANCH_A, "commit_sha": COMMIT_A, "tree_sha": TREE_A},
            "the recorded head is not the head the repository reported",
        )

    def test_capture_refuses_when_any_head_dimension_moves_before_sealing(self) -> None:
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        moves = {
            "commit_sha": {"head": [{"stdout": f"{COMMIT_A}\n"}, {"stdout": f"{COMMIT_B}\n"}]},
            "tree_sha": {"tree": [{"stdout": f"{TREE_A}\n"}, {"stdout": f"{TREE_B}\n"}]},
            "branch": {"branch": [{"stdout": f"{BRANCH_A}\n"}, {"stdout": f"{BRANCH_B}\n"}]},
        }
        for dimension, overrides in moves.items():
            with self.subTest(dimension=dimension):
                self.rescript_git(**overrides)
                result = self.capture()
                self.assertEqual(result["verdict"], REFUSED, f"a moved {dimension} was sealed anyway")
                self.assertIsNone(result["snapshot"], "a refused capture published a snapshot")
                self.assertIsNone(result["digest"], "a refused capture published a digest")
                joined = " ".join(result["reasons"])
                self.assertIn(f"head.{dimension}", joined, f"the refusal did not name head.{dimension}")
                stability = [entry for entry in result["checks"] if entry["slug"] == "head-stability"]
                self.assertEqual(len(stability), 1, "the anchor check was not reported exactly once")
                self.assertFalse(stability[0]["met"], "a moved head left the anchor check met")

    def test_capture_re_reads_the_head_after_every_other_observation(self) -> None:
        self.sealed()
        keys = [
            "head"
            if "rev-parse" in call["args"] and "HEAD" in call["args"]
            else "other"
            for call in self.calls()
        ]
        self.assertEqual(keys.count("head"), 2, f"the head was not read exactly twice: {keys}")
        last_head = max(index for index, key in enumerate(keys) if key == "head")
        status_calls = [index for index, call in enumerate(self.calls()) if "status" in call["args"]]
        self.assertTrue(status_calls, "the working tree was never observed")
        self.assertGreater(
            last_head, max(status_calls), "the head was re-read before the rest of the observation, not after"
        )

    def test_the_tree_is_derived_from_the_read_commit_not_a_second_head_read(self) -> None:
        """The atomicity fix: `rev-parse HEAD^{tree}` would read HEAD a second time, and an ABBA move
        between the commit read and that second read could seal a commit/tree pair never observed
        together. Deriving the tree from the COMMIT SHA this same call already read removes the
        second HEAD read entirely -- there is only one `HEAD` literal per `observe_head` call left to
        move, and the tree query always names the exact commit whose tree is being asked for."""
        self.sealed()
        tree_calls = [
            call["args"]
            for call in self.calls()
            if "rev-parse" in call["args"] and any(arg.endswith("^{tree}") for arg in call["args"])
        ]
        self.assertEqual(len(tree_calls), 2, f"the tree was not derived exactly twice: {tree_calls}")
        for args in tree_calls:
            self.assertNotIn(
                "HEAD^{tree}", args,
                "the tree was derived from a second independent HEAD read rather than the commit "
                "this same observation already read",
            )
            self.assertIn(
                f"{COMMIT_A}^{{tree}}", args,
                "the tree derivation did not name the exact commit this observation read",
            )

    def test_capture_validates_the_body_it_built_with_the_schema_verify_uses(self) -> None:
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.rescript_git(head={"stdout": "not-a-sha\n"})
        result = self.capture()
        self.assertEqual(result["verdict"], REFUSED, "an unusable object name was sealed as a head")
        self.assertIsNone(result["snapshot"], "a refused capture published a snapshot")
        unmet = [entry["slug"] for entry in result["checks"] if not entry["met"]]
        self.assertIn(
            "head-observation", unmet, "capture did not run the shape check verify would have run"
        )
        self.assertIn(
            "commit_sha", " ".join(result["reasons"]), "the refusal did not name the field that was unusable"
        )

    def test_a_detached_head_records_a_null_branch_and_names_it_unknown(self) -> None:
        control = self.sealed()
        self.assertIsNotNone(control["head"]["branch"], "the control capture recorded no branch")
        self.assertNotIn("head.branch", self.named(control), "an observed branch was also named unknown")
        self.rescript_git(branch={"stdout": "", "returncode": 1})
        sealed = self.sealed()
        self.assertIsNone(sealed["head"]["branch"], "a detached head recorded a branch it does not have")
        self.assertIn("head.branch", self.named(sealed), "a detached head did not name head.branch as unknown")

    def test_verify_refuses_a_snapshot_that_records_a_head_it_also_calls_unknown(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        both = dict(sealed)
        both["unknowns"] = sorted(
            sealed["unknowns"] + [{"dimension": "head.branch", "reason": "claimed unobserved"}],
            key=lambda entry: entry["dimension"],
        )
        refused = self.verify(self.reseal(both))
        self.assertEqual(refused["verdict"], REFUSED, "a value that was also unknown was verified")
        self.assertIn("head.branch", " ".join(refused["reasons"]), "the refusal did not name head.branch")

    def test_verify_refuses_a_detail_suffixed_alias_of_a_dimension_that_records_a_value(self) -> None:
        """A `:<detail>` suffix is admitted only on `policy_digests` and `wave_artifacts` -- the two
        dimensions `capture` ever digests one path at a time. Elsewhere the suffixed spelling is a
        DIFFERENT string from its base, so a document naming `head.branch:x` unknown while ALSO
        recording a value for `head.branch` must not slip past the exact-match naming check, which
        compares `head.branch` verbatim. The exact-string form -- a null head.branch named exactly,
        with no detail -- is the positive control proving the fix does not also refuse the legitimate
        case.
        """
        self.rescript_git(branch={"stdout": "", "returncode": 1})
        detached = self.sealed()
        self.assertIsNone(detached["head"]["branch"], "the fixture did not actually detach the head")
        control = self.verify(detached)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        self.rescript_git()
        valued = self.sealed()
        self.assertIsNotNone(valued["head"]["branch"], "the control capture recorded no branch")
        decorated = dict(valued)
        decorated["unknowns"] = sorted(
            valued["unknowns"] + [{"dimension": "head.branch:x", "reason": "claimed unobserved via detail"}],
            key=lambda entry: entry["dimension"],
        )
        refused = self.verify(self.reseal(decorated))
        self.assertEqual(
            refused["verdict"], REFUSED, "a detail-suffixed alias of a recorded dimension was verified"
        )
        self.assertIn(
            "head.branch:x", " ".join(refused["reasons"]), "the refusal did not name the decorated dimension"
        )
        with self.subTest(dimension="queue.sha256"):
            absent = valued
            self.assertEqual(absent["queue"]["state"], "absent", "the fixture queue was not actually absent")
            decorated_queue = dict(absent)
            decorated_queue["unknowns"] = sorted(
                absent["unknowns"]
                + [{"dimension": "queue.sha256:x", "reason": "claimed unobserved via detail"}],
                key=lambda entry: entry["dimension"],
            )
            refused_queue = self.verify(self.reseal(decorated_queue))
            self.assertEqual(
                refused_queue["verdict"], REFUSED, "a detail-suffixed queue.sha256 alias was verified"
            )
            self.assertIn(
                "queue.sha256:x", " ".join(refused_queue["reasons"]),
                "the refusal did not name the decorated dimension",
            )

    def test_verify_refuses_a_snapshot_that_omits_a_null_dimension_instead_of_naming_it(self) -> None:
        self.rescript_git(branch={"stdout": "", "returncode": 1})
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        silent = dict(sealed)
        silent["unknowns"] = [entry for entry in sealed["unknowns"] if entry["dimension"] != "head.branch"]
        refused = self.verify(self.reseal(silent))
        self.assertEqual(refused["verdict"], REFUSED, "a silently omitted dimension was verified")
        self.assertIn("head.branch", " ".join(refused["reasons"]), "the refusal did not name head.branch")


class NamedUnknownTests(_SnapshotTestCase):
    """Anything unobserved is named by name; nothing unobserved is guessed."""

    def test_every_snapshot_names_the_four_dimensions_this_tool_never_observes(self) -> None:
        named = self.named(self.sealed())
        for dimension in REQUIRED_UNKNOWNS:
            self.assertIn(dimension, named, f"{dimension} was silently omitted rather than named")
            self.assertTrue(named[dimension], f"{dimension} was named with an empty reason")
        self.assertNotIn(
            "policy_digests", named, "a directory that was read was also named unknown"
        )

    def test_verify_refuses_a_snapshot_that_stops_naming_a_never_observed_dimension(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        for dimension in REQUIRED_UNKNOWNS:
            with self.subTest(dimension=dimension):
                quiet = dict(sealed)
                quiet["unknowns"] = [
                    entry for entry in sealed["unknowns"] if entry["dimension"] != dimension
                ]
                refused = self.verify(self.reseal(quiet))
                self.assertEqual(refused["verdict"], REFUSED, f"a snapshot silent about {dimension} verified")
                self.assertIn(dimension, " ".join(refused["reasons"]), f"the refusal did not name {dimension}")

    def test_an_unusable_uv_is_a_named_unknown_rather_than_a_guessed_version(self) -> None:
        control = self.sealed()
        self.assertEqual(control["host_capabilities"]["uv"], "0.11.17", "the control probe read no uv version")
        self.assertNotIn("host_capabilities.uv", self.named(control), "a probed uv was also named unknown")
        self.uv = self.work / "no-such-uv"
        self.rescript_git()
        sealed = self.sealed()
        self.assertIsNone(sealed["host_capabilities"]["uv"], "an unusable uv produced a version anyway")
        self.assertIn(
            "host_capabilities.uv", self.named(sealed), "an unusable uv was not named as an unknown"
        )
        self.assertEqual(
            sealed["host_capabilities"]["python"],
            ".".join(str(part) for part in sys.version_info[:3]),
            "the recorded python version is not the interpreter that made the observations",
        )

    def test_verify_refuses_an_unknown_dimension_outside_the_closed_vocabulary(self) -> None:
        sealed = self.sealed()
        invented = dict(sealed)
        invented["unknowns"] = sorted(
            sealed["unknowns"] + [{"dimension": "vibes", "reason": "unmeasured"}],
            key=lambda entry: entry["dimension"],
        )
        refused = self.verify(self.reseal(invented))
        self.assertEqual(refused["verdict"], REFUSED, "a free-text unknown dimension was verified")
        self.assertIn("vibes", " ".join(refused["reasons"]), "the refusal did not name the invented dimension")

    def test_verify_refuses_an_unknowns_list_that_is_not_sorted_or_repeats_a_dimension(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        for label, entries in (
            ("reordered", list(reversed(sealed["unknowns"]))),
            ("repeated", sealed["unknowns"] + [sealed["unknowns"][-1]]),
        ):
            with self.subTest(shape=label):
                mutated = self.reseal({**sealed, "unknowns": entries})
                refused = self.verify(mutated)
                self.assertEqual(refused["verdict"], REFUSED, f"a {label} unknowns list was verified")
                self.assertIn("unknowns", " ".join(refused["reasons"]), "the refusal did not name unknowns")


class DirtyStateTests(_SnapshotTestCase):
    """Counts, never contents."""

    def test_the_dirty_state_counts_each_porcelain_class_and_records_no_path(self) -> None:
        status = (
            status_record("MM", "both.txt")
            + status_record("M.", "staged.txt")
            + status_record(".M", "unstaged.txt")
            + unmerged_record("conflicted.txt")
            + "? untracked.txt\0"
        )
        self.assertIn("staged.txt", status, "the fixture does not actually carry a path to leak")
        self.rescript_git(status={"stdout": status})
        sealed = self.sealed()
        self.assertEqual(
            sealed["dirty_state"],
            {"staged": 2, "unmerged": 1, "unstaged": 2, "untracked": 1},
            "the porcelain classes were not counted as git reports them",
        )
        for path in ("both.txt", "staged.txt", "unstaged.txt", "conflicted.txt", "untracked.txt"):
            self.assertNotIn(
                path.encode("ascii"), canonical(sealed), f"the snapshot leaked the path {path}"
            )

    def test_a_clean_tree_records_zeros_rather_than_omitting_the_dimension(self) -> None:
        sealed = self.sealed()
        self.assertEqual(
            sealed["dirty_state"],
            {"staged": 0, "unmerged": 0, "unstaged": 0, "untracked": 0},
            "a clean tree did not record four zero counts",
        )

    def test_capture_refuses_a_porcelain_record_it_cannot_classify(self) -> None:
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.rescript_git(status={"stdout": "9 nonsense\0"})
        result = self.capture()
        self.assertEqual(result["verdict"], REFUSED, "an unclassifiable porcelain record was counted anyway")
        self.assertNamesADimension(result["reasons"])

    def test_verify_refuses_a_negative_or_non_integer_count(self) -> None:
        sealed = self.sealed()
        for label, value in (("negative", -1), ("boolean", True), ("string", "1")):
            with self.subTest(shape=label):
                mutated = self.reseal({**sealed, "dirty_state": {**sealed["dirty_state"], "staged": value}})
                refused = self.verify(mutated)
                self.assertEqual(refused["verdict"], REFUSED, f"a {label} count was verified")
                self.assertIn("staged", " ".join(refused["reasons"]), "the refusal did not name the count")


class WorktreeCustodyTests(_SnapshotTestCase):
    """Custody is the whole set of worktrees, in one spelling."""

    def test_worktrees_are_recorded_sorted_by_path_with_branch_and_head(self) -> None:
        second = self.work / "b-linked"
        third = self.work / "a-linked"
        self.rescript_git(
            worktrees={
                "stdout": worktree_entry(str(self.root))
                + worktree_entry(str(second), head=COMMIT_B, branch=BRANCH_B)
                + worktree_entry(str(third), head=COMMIT_B, branch=None)
            }
        )
        sealed = self.sealed()
        paths = [entry["path"] for entry in sealed["worktrees"]]
        self.assertEqual(paths, sorted(paths), "the worktree list is not sorted by path")
        self.assertEqual(len(paths), 3, f"not every reported worktree was recorded: {paths}")
        by_path = {entry["path"]: entry for entry in sealed["worktrees"]}
        self.assertEqual(
            by_path[str(second)], {"branch": BRANCH_B, "head": COMMIT_B, "path": str(second)},
            "a linked worktree's branch or head was not recorded as reported",
        )
        self.assertIsNone(by_path[str(third)]["branch"], "a detached worktree was given a branch")
        self.assertIn(
            "worktrees.branch", self.named(sealed), "a detached worktree did not name worktrees.branch"
        )
        self.assertNotIn("worktrees.head", self.named(sealed), "an observed head was named unknown")

    def test_a_bare_worktree_records_a_null_head_and_names_it_unknown(self) -> None:
        control = self.sealed()
        self.assertNotIn("worktrees.head", self.named(control), "the control named an observed head unknown")
        self.rescript_git(worktrees={"stdout": worktree_entry(str(self.root), head=None, branch=None)})
        sealed = self.sealed()
        self.assertIsNone(sealed["worktrees"][0]["head"], "a bare worktree was given a head")
        self.assertIn("worktrees.head", self.named(sealed), "a bare worktree did not name worktrees.head")

    def test_a_worktree_path_containing_a_newline_stays_one_worktree(self) -> None:
        odd = f"{self.work}/line\nbreak"
        self.rescript_git(worktrees={"stdout": worktree_entry(str(self.root)) + worktree_entry(odd)})
        sealed = self.sealed()
        self.assertEqual(len(sealed["worktrees"]), 2, "a NUL-delimited path with a newline was split")
        self.assertIn(odd, [entry["path"] for entry in sealed["worktrees"]], "the odd path was not recorded")

    def test_verify_refuses_a_worktree_list_that_is_not_sorted_or_repeats_a_path(self) -> None:
        second = self.work / "b-linked"
        self.rescript_git(
            worktrees={
                "stdout": worktree_entry(str(self.root)) + worktree_entry(str(second), branch=BRANCH_B)
            }
        )
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        for label, entries in (
            ("reordered", list(reversed(sealed["worktrees"]))),
            ("repeated", [sealed["worktrees"][0], sealed["worktrees"][0]]),
        ):
            with self.subTest(shape=label):
                refused = self.verify(self.reseal({**sealed, "worktrees": entries}))
                self.assertEqual(refused["verdict"], REFUSED, f"a {label} worktree list was verified")
                self.assertIn("worktrees", " ".join(refused["reasons"]), "the refusal did not name worktrees")

    def test_verify_refuses_a_relative_worktree_path(self) -> None:
        sealed = self.sealed()
        entry = {**sealed["worktrees"][0], "path": "repo"}
        refused = self.verify(self.reseal({**sealed, "worktrees": [entry]}))
        self.assertEqual(refused["verdict"], REFUSED, "a relative custody path was verified")
        self.assertIn("absolute", " ".join(refused["reasons"]), "the refusal did not say why the path is unusable")

    def test_verify_refuses_an_empty_worktrees_list(self) -> None:
        """`git worktree list` always reports at least the observed worktree itself, so `capture`
        can never produce an empty list; `verify` must refuse a hand-crafted one rather than admit a
        shape that is otherwise a well-formed empty JSON list."""
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        refused = self.verify(self.reseal({**sealed, "worktrees": []}))
        self.assertEqual(refused["verdict"], REFUSED, "an empty worktrees list was verified")
        self.assertIn("worktrees", " ".join(refused["reasons"]), "the refusal did not name worktrees")

    def test_verify_refuses_a_nul_or_newline_bearing_branch_string(self) -> None:
        """No `git check-ref-format`-legal ref name carries a control character, so a NUL or a
        newline in a recorded branch is a shape `capture` could never have observed -- for either
        `head.branch` or a `worktrees[].branch`."""
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        for label, branch in (("newline", "feature/one\ntwo"), ("nul", "feature/one\x00two")):
            with self.subTest(field="head.branch", shape=label):
                mutated = self.reseal({**sealed, "head": {**sealed["head"], "branch": branch}})
                refused = self.verify(mutated)
                self.assertEqual(refused["verdict"], REFUSED, f"a {label}-bearing head.branch was verified")
                self.assertIn("branch", " ".join(refused["reasons"]), "the refusal did not name branch")
            with self.subTest(field="worktrees[].branch", shape=label):
                entry = {**sealed["worktrees"][0], "branch": branch}
                refused = self.verify(self.reseal({**sealed, "worktrees": [entry]}))
                self.assertEqual(
                    refused["verdict"], REFUSED, f"a {label}-bearing worktrees branch was verified"
                )
                self.assertIn("branch", " ".join(refused["reasons"]), "the refusal did not name branch")


class QueueStateTests(_SnapshotTestCase):
    """The queue has three shapes, and absence observed is not absence of observation."""

    def write_queue(self, text: str) -> Path:
        target = self.root / ".seeds" / "issues.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def test_an_absent_queue_is_an_explicit_shape_that_names_no_unknown(self) -> None:
        sealed = self.sealed()
        self.assertEqual(
            sealed["queue"],
            {"path": ".seeds/issues.jsonl", "records": None, "sha256": None, "state": "absent"},
            "an absent queue was not recorded as its own explicit shape",
        )
        named = self.named(sealed)
        self.assertNotIn("queue.sha256", named, "an absent queue named its digest unknown")
        self.assertNotIn("queue.records", named, "an absent queue named its record count unknown")

    def test_a_present_queue_records_its_digest_and_its_record_count(self) -> None:
        queue = self.write_queue('{"id":"one"}\n{"id":"two"}\n\n{"id":"three"}\n')
        sealed = self.sealed()
        self.assertEqual(sealed["queue"]["state"], "present", "a present queue was not recorded as present")
        self.assertEqual(
            sealed["queue"]["sha256"],
            hashlib.sha256(queue.read_bytes()).hexdigest(),
            "the recorded queue digest is not sha256 over the queue's bytes",
        )
        self.assertEqual(sealed["queue"]["records"], 3, "the record count did not skip the blank line")
        self.assertNotIn("queue.records", self.named(sealed), "a derived count was also named unknown")

    def test_a_queue_line_that_is_not_one_json_object_makes_only_the_count_unknown(self) -> None:
        self.write_queue('{"id":"one"}\n')
        control = self.sealed()
        self.assertEqual(control["queue"]["records"], 1, "the control queue did not count its one record")
        self.write_queue('{"id":"one"}\nnot json at all\n')
        self.rescript_git()
        sealed = self.sealed()
        self.assertIsNone(sealed["queue"]["records"], "an unparsable line still produced a count")
        self.assertIsNotNone(sealed["queue"]["sha256"], "an unparsable line also discarded the digest")
        named = self.named(sealed)
        self.assertIn("queue.records", named, "an underivable count was not named unknown")
        self.assertIn("line 2", named["queue.records"], "the reason did not name which line could not be read")
        self.assertNotIn("not json at all", canonical(sealed).decode("ascii"), "the queue's bytes leaked")

    def test_a_queue_that_is_not_a_regular_file_is_unreadable_and_names_both_dimensions(self) -> None:
        (self.root / ".seeds" / "issues.jsonl").mkdir(parents=True)
        sealed = self.sealed()
        self.assertEqual(sealed["queue"]["state"], "unreadable", "a directory queue was called present")
        named = self.named(sealed)
        self.assertIn("queue.sha256", named, "an unreadable queue did not name its digest unknown")
        self.assertIn("queue.records", named, "an unreadable queue did not name its count unknown")

    def test_verify_refuses_an_absent_queue_that_names_its_digest_unknown(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        confused = dict(sealed)
        confused["unknowns"] = sorted(
            sealed["unknowns"] + [{"dimension": "queue.sha256", "reason": "claimed unobserved"}],
            key=lambda entry: entry["dimension"],
        )
        refused = self.verify(self.reseal(confused))
        self.assertEqual(refused["verdict"], REFUSED, "an absent queue naming an unknown digest verified")
        self.assertIn("queue.sha256", " ".join(refused["reasons"]), "the refusal did not name queue.sha256")

    def test_verify_refuses_a_queue_path_other_than_the_pinned_canonical_path(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        pinned = dict(sealed["queue"])
        self.assertEqual(pinned["path"], ".seeds/issues.jsonl", "the fixture queue does not carry the pinned path")
        mutated = self.reseal({**sealed, "queue": {**pinned, "path": "elsewhere/queue.jsonl"}})
        refused = self.verify(mutated)
        self.assertEqual(refused["verdict"], REFUSED, "a queue.path other than the one queue this schema owns was verified")
        self.assertIn("queue.path", " ".join(refused["reasons"]), "the refusal did not name queue.path")

    def test_verify_refuses_a_present_queue_with_no_digest_and_an_unlisted_state(self) -> None:
        self.write_queue('{"id":"one"}\n')
        sealed = self.sealed()
        for label, queue in (
            ("digestless", {**sealed["queue"], "sha256": None}),
            ("invented state", {**sealed["queue"], "state": "probably-fine"}),
        ):
            with self.subTest(shape=label):
                refused = self.verify(self.reseal({**sealed, "queue": queue}))
                self.assertEqual(refused["verdict"], REFUSED, f"a {label} queue was verified")
                self.assertIn("queue", " ".join(refused["reasons"]), "the refusal did not name the queue")


class LocalEvidenceTests(_SnapshotTestCase):
    """Policy and wave artifacts are the files present, digested where they can be read."""

    def test_policy_and_wave_artifact_digests_are_the_json_files_present(self) -> None:
        (self.root / "policy").mkdir()
        (self.root / ".sdlc").mkdir()
        first = self.root / "policy" / "b-second.json"
        second = self.root / "policy" / "a-first.json"
        first.write_text('{"one":1}', encoding="utf-8")
        second.write_text('{"two":2}', encoding="utf-8")
        (self.root / "policy" / "notes.md").write_text("not json", encoding="utf-8")
        wave = self.root / ".sdlc" / "wave.json"
        wave.write_text('{"wave":1}', encoding="utf-8")
        sealed = self.sealed()
        self.assertEqual(
            sealed["policy_digests"],
            [
                {"path": "policy/a-first.json", "sha256": hashlib.sha256(second.read_bytes()).hexdigest()},
                {"path": "policy/b-second.json", "sha256": hashlib.sha256(first.read_bytes()).hexdigest()},
            ],
            "the policy digests are not the present json files in path order",
        )
        self.assertEqual(
            sealed["wave_artifacts"],
            [{"path": ".sdlc/wave.json", "sha256": hashlib.sha256(wave.read_bytes()).hexdigest()}],
            "the wave artifacts are not the present json files",
        )

    def test_an_absent_directory_is_an_empty_observation_rather_than_an_unknown(self) -> None:
        sealed = self.sealed()
        self.assertEqual(sealed["policy_digests"], [], "an absent policy directory produced entries")
        self.assertEqual(sealed["wave_artifacts"], [], "an absent .sdlc directory produced entries")
        named = self.named(sealed)
        self.assertNotIn("policy_digests", named, "a directory that is simply absent was named unknown")
        self.assertNotIn("wave_artifacts", named, "a directory that is simply absent was named unknown")

    def test_a_symlinked_policy_file_is_named_unknown_rather_than_followed(self) -> None:
        (self.root / "policy").mkdir()
        outside = self.work / "outside.json"
        outside.write_text('{"outside":true}', encoding="utf-8")
        link = self.root / "policy" / "linked.json"
        try:
            link.symlink_to(outside)
        except OSError as exc:  # pragma: no cover - platform without user-creatable symlinks
            self.skipTest(f"symlinks are unavailable here: {exc}")
        real = self.root / "policy" / "real.json"
        real.write_text('{"real":true}', encoding="utf-8")
        sealed = self.sealed()
        self.assertEqual(
            [entry["path"] for entry in sealed["policy_digests"]],
            ["policy/real.json"],
            "a symlink was digested as though it were a repository file",
        )
        named = self.named(sealed)
        self.assertIn(
            "policy_digests:policy/linked.json", named, "a skipped symlink was not named by its own path"
        )
        self.assertNotIn(
            hashlib.sha256(outside.read_bytes()).hexdigest(),
            canonical(sealed).decode("ascii"),
            "the symlink's target was digested through the link",
        )
        # `policy_digests` is one of the two dimensions a `:<detail>` suffix is admitted on, so the
        # decorated name this capture actually named unknown must still verify.
        verified = self.verify(sealed)
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])

    def test_an_unreadable_wave_artifact_is_named_unknown_rather_than_dropped(self) -> None:
        """Regression for the seed where `wave_artifacts` is observed AFTER `unknowns.entries()` is
        taken in the `observe()` body literal: an unknown this observation names must still land in
        the sealed `unknowns` list, not just be produced and then discarded."""
        if os.geteuid() == 0:
            self.skipTest("root bypasses file permissions, so the probe cannot fail")
        (self.root / ".sdlc").mkdir()
        blocked = self.root / ".sdlc" / "wave-journal.json"
        blocked.write_text('{"wave":1}', encoding="utf-8")
        blocked.chmod(0o000)
        self.addCleanup(blocked.chmod, 0o644)
        readable = self.root / ".sdlc" / "wave-plan.json"
        readable.write_text('{"plan":1}', encoding="utf-8")

        sealed = self.sealed()

        self.assertEqual(
            [entry["path"] for entry in sealed["wave_artifacts"]],
            [".sdlc/wave-plan.json"],
            "the unreadable wave artifact was digested as though it could be read",
        )
        named = self.named(sealed)
        self.assertIn(
            "wave_artifacts:.sdlc/wave-journal.json",
            named,
            "an unknown that observe_file_digests named for the unreadable artifact was dropped "
            "from the sealed document",
        )
        # Positive control: the readable artifact in the same directory IS digested and is NOT
        # named unknown, so the assertion above is about the permission failure, not a directory
        # this tool never observes at all.
        self.assertNotIn(
            "wave_artifacts:.sdlc/wave-plan.json",
            named,
            "a readable wave artifact was named unknown alongside the unreadable one",
        )
        self.assertIn(
            {"path": ".sdlc/wave-plan.json", "sha256": hashlib.sha256(readable.read_bytes()).hexdigest()},
            sealed["wave_artifacts"],
            "the readable wave artifact was not digested",
        )
        # `wave_artifacts` is the other dimension a `:<detail>` suffix is admitted on, so the
        # decorated name this capture actually named unknown must still verify.
        verified = self.verify(sealed)
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])

    def test_verify_refuses_a_policy_digests_list_that_is_not_sorted_by_path(self) -> None:
        (self.root / "policy").mkdir()
        (self.root / "policy" / "a-first.json").write_text('{"a":1}', encoding="utf-8")
        (self.root / "policy" / "b-second.json").write_text('{"b":2}', encoding="utf-8")
        sealed = self.sealed()
        self.assertEqual(
            len(sealed["policy_digests"]), 2, "the fixture does not carry two entries to reorder"
        )
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        reordered = self.reseal({**sealed, "policy_digests": list(reversed(sealed["policy_digests"]))})
        refused = self.verify(reordered)
        self.assertEqual(refused["verdict"], REFUSED, "a reordered policy_digests list was verified")
        self.assertIn(
            "policy_digests", " ".join(refused["reasons"]), "the refusal did not name policy_digests"
        )

    def test_verify_refuses_a_digest_entry_whose_path_escapes_the_repository(self) -> None:
        (self.root / "policy").mkdir()
        (self.root / "policy" / "real.json").write_text("{}", encoding="utf-8")
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        for label, path in (("absolute", "/etc/policy.json"), ("parent-relative", "../policy/real.json")):
            with self.subTest(shape=label):
                entry = {**sealed["policy_digests"][0], "path": path}
                refused = self.verify(self.reseal({**sealed, "policy_digests": [entry]}))
                self.assertEqual(refused["verdict"], REFUSED, f"a {label} digest path was verified")
                self.assertIn(
                    "policy_digests", " ".join(refused["reasons"]), "the refusal did not name policy_digests"
                )


class OutputPathTests(_SnapshotTestCase):
    """The one write: exclusive, outside the observed tree, and never a repository mutation."""

    def tree_state(self) -> dict[str, str]:
        state: dict[str, str] = {}
        for path in sorted(self.root.rglob("*")):
            relative = str(path.relative_to(self.root))
            state[relative] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "<directory>"
            )
        return state

    def test_out_receives_the_canonical_sealed_snapshot_and_stdout_still_carries_the_result(self) -> None:
        target = self.work / "out" / "snapshot.json"
        target.parent.mkdir()
        result = self.capture("--out", str(target))
        self.assertEqual(result["verdict"], CAPTURED, result["reasons"])
        self.assertEqual(result["out"], str(target), "the result did not name the file it wrote")
        self.assertEqual(
            target.read_bytes(), canonical(result["snapshot"]), "the written file is not the canonical sealed form"
        )
        verified = self.verify(target.read_bytes())
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])

    def test_an_occupied_out_path_is_refused_and_left_exactly_as_it_was(self) -> None:
        target = self.work / "out" / "snapshot.json"
        target.parent.mkdir()
        target.write_bytes(b"prior evidence\n")
        result = self.capture("--out", str(target))
        self.assertEqual(result["verdict"], REFUSED, "an occupied destination was overwritten")
        self.assertIsNone(result["snapshot"], "a refused capture published a snapshot")
        self.assertEqual(target.read_bytes(), b"prior evidence\n", "the occupied destination was modified")
        self.assertIn("--out", " ".join(result["reasons"]), "the refusal did not name the option")

    def test_a_dangling_symlink_at_out_is_refused_rather_than_written_through(self) -> None:
        target = self.work / "out" / "snapshot.json"
        target.parent.mkdir()
        victim = self.work / "victim.json"
        try:
            target.symlink_to(victim)
        except OSError as exc:  # pragma: no cover - platform without user-creatable symlinks
            self.skipTest(f"symlinks are unavailable here: {exc}")
        result = self.capture("--out", str(target))
        self.assertEqual(result["verdict"], REFUSED, "a dangling symlink at --out was written through")
        self.assertFalse(victim.exists(), "the symlink's target was created")

    def test_an_out_path_inside_the_observed_repository_is_refused(self) -> None:
        outside = self.work / "outside.json"
        control = self.capture("--out", str(outside))
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.rescript_git()
        inside = self.root / "snapshot.json"
        result = self.capture("--out", str(inside))
        self.assertEqual(result["verdict"], REFUSED, "the snapshot was written into the tree it describes")
        self.assertFalse(inside.exists(), "a refused capture created its output anyway")
        self.assertIn("worktree_path", " ".join(result["reasons"]), "the refusal did not name what it collided with")

    def test_an_out_path_whose_symlinked_parent_resolves_inside_the_repository_is_refused(self) -> None:
        inside = self.root / "inside-dir"
        inside.mkdir()
        linked_parent = self.work / "linked-parent"
        try:
            linked_parent.symlink_to(inside)
        except OSError as exc:  # pragma: no cover - platform without user-creatable symlinks
            self.skipTest(f"symlinks are unavailable here: {exc}")
        target = linked_parent / "snapshot.json"
        result = self.capture("--out", str(target))
        self.assertEqual(
            result["verdict"], REFUSED,
            "the snapshot was written into the observed repository through a symlinked --out parent",
        )
        self.assertFalse(
            (inside / "snapshot.json").exists(), "a refused capture wrote through the symlinked parent anyway"
        )
        self.assertIn("worktree_path", " ".join(result["reasons"]), "the refusal did not name what it collided with")
        # Positive control: a symlinked parent that resolves OUTSIDE the repository still writes.
        outside = self.work / "outside-dir"
        outside.mkdir()
        linked_elsewhere = self.work / "linked-elsewhere"
        linked_elsewhere.symlink_to(outside)
        self.rescript_git()
        control_target = linked_elsewhere / "snapshot.json"
        control = self.capture("--out", str(control_target))
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.assertTrue(
            (outside / "snapshot.json").exists(),
            "a capture through a symlinked parent resolving outside the repository did not write",
        )

    def test_an_out_path_inside_the_observed_git_directory_is_refused(self) -> None:
        inside = self.root / ".git" / "snapshot.json"
        result = self.capture("--out", str(inside))
        self.assertEqual(result["verdict"], REFUSED, "the snapshot was written into the observed git directory")
        self.assertFalse(inside.exists(), "a refused capture created its output anyway")
        self.assertIn("git_dir", " ".join(result["reasons"]), "the refusal did not name what it collided with")

    def test_an_out_path_with_no_parent_directory_is_refused_before_any_write(self) -> None:
        target = self.work / "missing" / "snapshot.json"
        result = self.capture("--out", str(target))
        self.assertEqual(result["verdict"], REFUSED, "a snapshot was claimed for a path with nowhere to land")
        self.assertFalse(target.parent.exists(), "a refused capture created a directory")

    def test_capture_writes_nothing_into_the_observed_repository(self) -> None:
        (self.root / "policy").mkdir()
        (self.root / "policy" / "real.json").write_text("{}", encoding="utf-8")
        (self.root / ".seeds").mkdir()
        (self.root / ".seeds" / "issues.jsonl").write_text('{"id":"one"}\n', encoding="utf-8")
        before = self.tree_state()
        result = self.capture("--out", str(self.work / "snapshot.json"))
        self.assertEqual(result["verdict"], CAPTURED, result["reasons"])
        self.assertEqual(self.tree_state(), before, "capture changed the repository it only observes")


class ArgumentTests(_SnapshotTestCase):
    """An unusable argument is the QUESTION being unusable: exit 2, and no result document."""

    def test_a_stated_instant_that_is_not_the_familys_form_is_an_input_error(self) -> None:
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.rescript_git()
        for label, value in (
            ("no zone", "2026-08-20T01:00:00"),
            ("offset", "2026-08-20T01:00:00+00:00"),
            ("date only", "2026-08-20"),
            ("trailing text", "2026-08-20T01:00:00Z "),
        ):
            with self.subTest(shape=label):
                proc = self.run_tool(
                    "capture", "--repository", str(self.root), "--at", value, "--git", str(self.git)
                )
                self.assertEqual(proc.returncode, EXIT_INPUT, f"a {label} instant was accepted")
                self.assertEqual(proc.stdout, b"", "an unusable argument still produced a result document")
                self.assertIn("--at", proc.stderr.decode("utf-8"), "the diagnostic did not name the option")

    def test_a_unicode_digit_instant_is_refused_rather_than_read_as_a_number(self) -> None:
        """`\\d` matches every Unicode Nd digit; `[0-9]` is why this cannot be mistaken for an instant."""
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.rescript_git()
        arabic = "٢٠٢٦-08-20T01:00:00Z"
        self.assertTrue(arabic[0].isdigit(), "the fixture is not made of Unicode digits at all")
        proc = self.run_tool(
            "capture", "--repository", str(self.root), "--at", arabic, "--git", str(self.git)
        )
        self.assertEqual(proc.returncode, EXIT_INPUT, "a Unicode-digit instant was accepted as an instant")
        self.assertEqual(proc.stdout, b"", "a Unicode-digit instant still produced a result document")

    def test_a_unicode_digit_expect_digest_is_refused_rather_than_read_as_hexadecimal(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed, "--expect-digest", sealed["digest"])
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        arabic = "٠" * 64
        self.assertTrue(arabic[0].isdigit(), "the fixture is not made of Unicode digits at all")
        proc = self.run_tool(
            "verify", "--snapshot", str(self.work / "supplied.json"), "--expect-digest", arabic
        )
        self.assertEqual(proc.returncode, EXIT_INPUT, "a Unicode-digit digest was accepted as hexadecimal")
        self.assertEqual(proc.stdout, b"", "an unusable argument still produced a result document")
        self.assertNotEqual(sealed["digest"], arabic, "the fixture digest collided with the counter-example")

    def test_a_repository_that_is_not_a_directory_is_an_input_error(self) -> None:
        missing = self.work / "no-such-tree"
        proc = self.run_tool(
            "capture", "--repository", str(missing), "--at", AT, "--git", str(self.git), "--uv", str(self.uv)
        )
        self.assertEqual(proc.returncode, EXIT_INPUT, "a nonexistent repository was observed anyway")
        self.assertEqual(proc.stdout, b"", "an unusable argument still produced a result document")
        self.assertIn("--repository", proc.stderr.decode("utf-8"), "the diagnostic did not name the option")

    def test_an_unusable_git_executable_is_a_named_refusal_rather_than_a_traceback(self) -> None:
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        proc = self.run_tool(
            "capture", "--repository", str(self.root), "--at", AT,
            "--git", str(self.work / "no-such-git"), "--uv", str(self.uv),
        )
        self.assertEqual(proc.returncode, EXIT_OK, "an unusable git was not reported as a result")
        result = self.document(proc)
        self.assertEqual(result["verdict"], REFUSED, "an unusable git produced a snapshot")
        self.assertNotIn("Traceback", proc.stderr.decode("utf-8"), "an unusable git raised out of the tool")
        self.assertIn("no-such-git", " ".join(result["reasons"]), "the refusal did not name the executable")

    def test_a_git_that_exits_nonzero_is_a_named_refusal(self) -> None:
        control = self.capture()
        self.assertEqual(control["verdict"], CAPTURED, control["reasons"])
        self.rescript_git(toplevel={"stdout": "", "returncode": 128})
        result = self.capture()
        self.assertEqual(result["verdict"], REFUSED, "a failing git observation was sealed anyway")
        self.assertIsNone(result["snapshot"], "a refused capture published a snapshot")
        self.assertNamesADimension(result["reasons"])

    def test_a_missing_subcommand_is_a_usage_error_on_stderr_only(self) -> None:
        proc = self.run_tool()
        self.assertEqual(proc.returncode, EXIT_INPUT, "a missing subcommand did not exit 2")
        self.assertEqual(proc.stdout, b"", "usage text was written where the result document lives")
        self.assertIn("usage", proc.stderr.decode("utf-8").lower(), "no usage was reported")


class SuppliedDocumentTests(_SnapshotTestCase):
    """`verify` reads one JSON object, and says so when it was handed something else."""

    def test_verify_refuses_a_digest_the_documents_own_content_does_not_derive(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        edited = {**sealed, "stated_at": "2026-08-20T02:00:00Z"}
        refused = self.verify(edited)
        self.assertEqual(refused["verdict"], REFUSED, "an edited snapshot re-derived its own digest")
        self.assertIn(sealed["digest"], " ".join(refused["reasons"]), "the refusal did not name the recorded digest")

    def test_verify_refuses_a_missing_field_and_an_unknown_field(self) -> None:
        sealed = self.sealed()
        control = self.verify(sealed)
        self.assertEqual(control["verdict"], VERIFIED, control["reasons"])
        for label, mutated in (
            ("missing", {key: value for key, value in sealed.items() if key != "queue"}),
            ("unknown", {**sealed, "vibes": "excellent"}),
            ("digestless", {key: value for key, value in sealed.items() if key != "digest"}),
        ):
            with self.subTest(shape=label):
                refused = self.verify(self.reseal(mutated) if label != "digestless" else mutated)
                self.assertEqual(refused["verdict"], REFUSED, f"a {label} field was verified")
                self.assertNamesADimension(refused["reasons"])

    def test_verify_refuses_another_schema_version(self) -> None:
        sealed = self.sealed()
        refused = self.verify(self.reseal({**sealed, "schema": "agentic-sdlc/planning-snapshot@2"}))
        self.assertEqual(refused["verdict"], REFUSED, "a snapshot of another schema version was verified")
        self.assertIn("schema", " ".join(refused["reasons"]), "the refusal did not name the schema")

    def test_verify_refuses_a_non_finite_number_with_no_constant_token(self) -> None:
        sealed = self.sealed()
        raw = canonical(sealed).decode("ascii")
        finite = raw.replace('"staged":0', '"staged":1e40', 1)
        self.assertNotEqual(finite, raw, "the control substitution did not apply")
        control = self.verify(finite.encode("ascii"))
        self.assertEqual(control["verdict"], REFUSED, "a finite oddity was not merely refused")
        overflowing = raw.replace('"staged":0', '"staged":1e400', 1)
        proc = self.run_tool("verify", "--snapshot", str(self.store(overflowing)))
        self.assertEqual(proc.returncode, EXIT_INPUT, "an overflowing number was not an input error")
        self.assertNotIn("Traceback", proc.stderr.decode("utf-8"), "an overflowing number raised out of the tool")
        self.assertEqual(proc.stdout, b"", "an unusable document still produced a result document")

    def test_verify_refuses_the_non_finite_constant_tokens(self) -> None:
        sealed = self.sealed()
        raw = canonical(sealed).decode("ascii")
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                mutated = raw.replace('"staged":0', f'"staged":{token}', 1)
                self.assertNotEqual(mutated, raw, "the substitution did not apply")
                proc = self.run_tool("verify", "--snapshot", str(self.store(mutated)))
                self.assertEqual(proc.returncode, EXIT_INPUT, f"the constant {token} was accepted")
                self.assertNotIn("Traceback", proc.stderr.decode("utf-8"), f"{token} raised out of the tool")

    def test_verify_refuses_a_repeated_json_key(self) -> None:
        sealed = self.sealed()
        raw = canonical(sealed).decode("ascii")
        doubled = raw.replace('"schema":', '"schema":"agentic-sdlc/planning-snapshot@1","schema":', 1)
        self.assertNotEqual(doubled, raw, "the substitution did not apply")
        proc = self.run_tool("verify", "--snapshot", str(self.store(doubled)))
        self.assertEqual(proc.returncode, EXIT_INPUT, "a document with two meanings was read as one")
        self.assertIn("repeats", proc.stderr.decode("utf-8"), "the diagnostic did not say what was wrong")

    def test_verify_refuses_a_document_that_is_not_one_json_object(self) -> None:
        for label, payload in (("list", b"[]\n"), ("scalar", b"7\n"), ("garbage", b"{not json\n")):
            with self.subTest(shape=label):
                proc = self.run_tool("verify", "--snapshot", str(self.store(payload.decode("ascii"))))
                self.assertEqual(proc.returncode, EXIT_INPUT, f"a {label} document was read as a snapshot")
                self.assertEqual(proc.stdout, b"", "an unusable document still produced a result document")

    def test_verify_refuses_a_snapshot_path_that_is_not_a_regular_file(self) -> None:
        directory = self.work / "not-a-file"
        directory.mkdir()
        proc = self.run_tool("verify", "--snapshot", str(directory))
        self.assertEqual(proc.returncode, EXIT_INPUT, "a directory was read as a snapshot")
        self.assertIn("regular file", proc.stderr.decode("utf-8"), "the diagnostic did not say what was wrong")

    def store(self, text: str) -> Path:
        target = self.work / "supplied-raw.json"
        target.write_text(text, encoding="utf-8")
        return target


class CanonicalFormTests(_SnapshotTestCase):
    """The canonical form is BYTES: sorted, tight, ASCII, one trailing newline."""

    def test_a_non_ascii_branch_name_is_escaped_in_both_the_document_and_the_file(self) -> None:
        self.rescript_git(branch={"stdout": "feature/été\n"})
        target = self.work / "snapshot.json"
        result = self.capture("--out", str(target))
        self.assertEqual(result["verdict"], CAPTURED, result["reasons"])
        self.assertEqual(result["snapshot"]["head"]["branch"], "feature/été", "the branch was not recorded")
        written = target.read_bytes()
        self.assertNotIn("é".encode("utf-8"), written, "the written file is not ensure_ascii canonical")
        self.assertIn(b"\\u00e9", written, "the non-ASCII character was not escaped")
        self.assertTrue(written.endswith(b"}\n"), "the written file does not end with exactly one newline")
        self.assertEqual(written.count(b"\n"), 1, "the written file carries more than one newline")
        verified = self.verify(written)
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])
        self.assertEqual(
            verified["digest"], result["digest"], "the escaped form does not re-derive the same digest"
        )

    def test_input_key_order_and_whitespace_cannot_move_the_digest(self) -> None:
        sealed = self.sealed()
        pretty = json.dumps(dict(reversed(list(sealed.items()))), indent=3).encode("utf-8")
        self.assertNotEqual(pretty, canonical(sealed), "the reordered form is byte-identical to the canonical one")
        verified = self.verify(pretty)
        self.assertEqual(verified["verdict"], VERIFIED, verified["reasons"])
        self.assertEqual(verified["digest"], sealed["digest"], "reformatting the input moved the digest")


class EnvironmentAndSourceTests(_SnapshotTestCase):
    """The observation is the tool's, not the caller's shell's, and the tool imports no sibling."""

    def test_a_git_control_variable_in_the_callers_environment_does_not_reach_git(self) -> None:
        hostile = {
            "GIT_DIR": str(self.work / "hijacked"),
            "GIT_WORK_TREE": str(self.work / "hijacked"),
            "GIT_CONFIG_GLOBAL": str(self.work / "hijacked.gitconfig"),
            "GIT_INDEX_FILE": str(self.work / "hijacked.index"),
        }
        proc = self.run_tool(
            "capture", "--repository", str(self.root), "--at", AT, "--git", str(self.git), "--uv", str(self.uv),
            env=hostile,
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr.decode("utf-8"))
        self.assertEqual(self.document(proc)["verdict"], CAPTURED, "the control capture refused")
        seen = self.calls()
        self.assertTrue(seen, "git was never invoked, so nothing about its environment was proved")
        for call in seen:
            for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
                self.assertNotIn(name, call["env"], f"the caller's {name} reached the observation")
            self.assertEqual(
                call["env"].get("GIT_CONFIG_GLOBAL"),
                os.devnull,
                "the caller's global config was not replaced by the null device",
            )
            self.assertEqual(call["env"].get("GIT_OPTIONAL_LOCKS"), "0", "git was allowed to take optional locks")
            self.assertIn("PATH", call["env"], "the exec-resolution PATH was not carried across")

    def test_git_is_invoked_in_the_observed_repository_not_the_callers_directory(self) -> None:
        self.sealed()
        for call in self.calls():
            if call["args"] == ["--version"]:
                continue
            self.assertEqual(
                Path(call["cwd"]).resolve(),
                self.root.resolve(),
                "an observation ran somewhere other than the repository it describes",
            )

    def test_the_tool_imports_only_the_standard_library_and_no_sibling_tool(self) -> None:
        tree = ast.parse(TOOL.read_text("utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertIn("hashlib", imported, "the digest is not derived from the standard library at all")
        self.assertLessEqual(
            imported,
            {
                "__future__",
                "argparse",
                "collections",
                "hashlib",
                "json",
                "math",
                "os",
                "pathlib",
                "re",
                "stat",
                "subprocess",
                "sys",
                "typing",
            },
            "the tool imports something outside the standard library set this family allows",
        )
        for sibling in ("mission_contract", "wave_journal", "runtime_assignment", "importlib"):
            self.assertNotIn(sibling, imported, f"the tool reaches into {sibling} instead of consuming output")

    def test_every_regex_in_the_tool_anchors_digits_as_an_ascii_class(self) -> None:
        source = TOOL.read_text("utf-8")
        self.assertIn("[0-9]", source, "the tool contains no ASCII digit class at all")
        self.assertNotIn(
            "\\d", source, "the tool uses \\d, which admits every Unicode Nd digit as a decimal digit"
        )


class UndeliveredResultTests(_SnapshotTestCase):
    """A result derived and not delivered is exit 1, and it says whether the file already landed."""

    def run_with_hostile_stdout(self, argv: list[str]) -> tuple[int, bytes]:
        """Run the tool with a stdout whose reader is already gone, so every write fails."""
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            child = subprocess.Popen(
                [sys.executable, "-B", str(TOOL), *argv],
                stdout=write_fd,
                stderr=subprocess.PIPE,
                cwd=str(self.elsewhere),
                env=constructed_environment(),
            )
        finally:
            os.close(write_fd)
        assert child.stderr is not None
        with child.stderr as stream:
            err = stream.read()
        return child.wait(), err

    def test_a_stdout_that_cannot_receive_the_result_exits_one_and_names_the_written_file(self) -> None:
        target = self.work / "snapshot.json"
        code, err = self.run_with_hostile_stdout(
            [
                "capture", "--repository", str(self.root), "--at", AT,
                "--git", str(self.git), "--uv", str(self.uv), "--out", str(target),
            ]
        )
        self.assertEqual(code, EXIT_INTERNAL, "an undelivered result did not exit 1")
        message = err.decode("utf-8")
        self.assertIn(str(target), message, "the diagnostic did not name the file that outlived the exit")
        self.assertNotIn("Traceback", message, "the broken stream raised out of the tool")
        self.assertEqual(
            target.read_bytes()[:1], b"{", "the sealed snapshot was not written before the failed delivery"
        )

    def test_a_refusal_with_a_broken_stdout_still_exits_one_without_writing(self) -> None:
        inside = self.root / "snapshot.json"
        code, err = self.run_with_hostile_stdout(
            [
                "capture", "--repository", str(self.root), "--at", AT,
                "--git", str(self.git), "--uv", str(self.uv), "--out", str(inside),
            ]
        )
        self.assertEqual(code, EXIT_INTERNAL, "an undelivered refusal did not exit 1")
        self.assertFalse(inside.exists(), "a refusal wrote its output when stdout was broken")
        self.assertNotIn("Traceback", err.decode("utf-8"), "the broken stream raised out of the tool")


@unittest.skipUnless(shutil.which("git"), "a real git is required to build a real repository fixture")
class RealRepositoryTests(unittest.TestCase):
    """One end-to-end pass over a real repository, so the scripted fixtures stay honest.

    This class is the only host-dependent one here and it is SKIPPED without git; every assertion
    about the tool's own behaviour lives in the scripted classes above, which run everywhere.
    """

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="planning-snapshot-real-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.root = self.work / "repo"
        self.root.mkdir()
        self.git(["init", "--quiet", "-b", "trunk", "."])
        (self.root / "tracked.txt").write_text("one\n", encoding="utf-8")
        self.git(["add", "tracked.txt"])
        self.git(["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", "one"])

    def git(self, args: list[str], *, cwd: Path | None = None) -> str:
        done = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.root),
            capture_output=True,
            check=False,
            env=constructed_environment(
                {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            ),
        )
        self.assertEqual(done.returncode, 0, f"git {args} failed: {done.stderr!r}")
        return done.stdout.decode("utf-8").strip()

    def test_a_real_repository_captures_its_actual_head_dirty_state_and_worktrees(self) -> None:
        linked = self.work / "linked"
        self.git(["worktree", "add", "--quiet", "-b", "side", str(linked)])
        (self.root / "tracked.txt").write_text("two\n", encoding="utf-8")
        self.git(["add", "tracked.txt"])
        (self.root / "tracked.txt").write_text("three\n", encoding="utf-8")
        (self.root / "untracked.txt").write_text("new\n", encoding="utf-8")
        target = self.work / "snapshot.json"
        proc = subprocess.run(
            [
                sys.executable, "-B", str(TOOL), "capture", "--repository", str(self.root),
                "--at", AT, "--out", str(target),
            ],
            capture_output=True,
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr.decode("utf-8"))
        result = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(result["verdict"], CAPTURED, result["reasons"])
        sealed = result["snapshot"]
        self.assertEqual(sealed["head"]["commit_sha"], self.git(["rev-parse", "HEAD"]), "the head commit is wrong")
        self.assertEqual(
            sealed["head"]["tree_sha"], self.git(["rev-parse", "HEAD^{tree}"]), "the head tree is wrong"
        )
        self.assertEqual(sealed["head"]["branch"], "trunk", "the branch is wrong")
        self.assertEqual(
            sealed["repository"]["worktree_path"], self.git(["rev-parse", "--show-toplevel"]), "the top level is wrong"
        )
        self.assertEqual(
            sealed["dirty_state"],
            {"staged": 1, "unmerged": 0, "unstaged": 1, "untracked": 1},
            "the dirty state does not match the tree that was built",
        )
        self.assertEqual(
            [entry["path"] for entry in sealed["worktrees"]],
            sorted([str(self.root), str(linked)]),
            "the custody summary is not the real worktree set",
        )
        self.assertEqual(
            {entry["path"]: entry["branch"] for entry in sealed["worktrees"]},
            {str(self.root): "trunk", str(linked): "side"},
            "a real worktree's branch was not recorded",
        )
        self.assertEqual(
            sealed["digest"], expected_digest(sealed), "the real capture's digest is not the contract's derivation"
        )
        verified = subprocess.run(
            [sys.executable, "-B", str(TOOL), "verify", "--snapshot", str(target),
             "--expect-digest", sealed["digest"]],
            capture_output=True,
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(verified.returncode, EXIT_OK, verified.stderr.decode("utf-8"))
        self.assertEqual(
            json.loads(verified.stdout.decode("utf-8"))["verdict"], VERIFIED, "a real snapshot did not verify"
        )

    def test_an_earlier_real_snapshot_durably_names_the_head_it_observed(self) -> None:
        """The recorded half of the anchor against real git. Moving HEAD mid-capture needs a scripted
        git, so what this proves is the durability the seed asks for: after a real commit, the earlier
        snapshot still names the exact earlier head, which is what makes staleness DETECTABLE. The
        enforcement half -- refusing a stale pair -- belongs to plan admission, not here."""
        first = subprocess.run(
            [sys.executable, "-B", str(TOOL), "capture", "--repository", str(self.root), "--at", AT],
            capture_output=True,
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(first.returncode, EXIT_OK, first.stderr.decode("utf-8"))
        before = json.loads(first.stdout.decode("utf-8"))["snapshot"]
        (self.root / "tracked.txt").write_text("moved\n", encoding="utf-8")
        self.git(["add", "tracked.txt"])
        self.git(["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", "two"])
        self.assertNotEqual(
            before["head"]["commit_sha"],
            self.git(["rev-parse", "HEAD"]),
            "the fixture did not actually move the head",
        )
        self.assertEqual(
            before["head"]["commit_sha"],
            self.git(["rev-parse", "HEAD~1"]),
            "the earlier snapshot does not durably name the exact head it observed",
        )


if __name__ == "__main__":
    unittest.main()
