#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Execute an EXTRACTED release archive's own ``bin/ccodex`` against a data-driven case manifest.

CONTRACT.

  * The subject is a tree that came out of ``scripts/build_release.py``'s archive, never this
    checkout.  ``--tree`` is refused when it resolves inside this repository, because a gate that
    exercised the checkout would prove nothing about the bytes an operator downloads -- that is the
    exact defect class this module exists for (issue #9: two prereleases shipped a ``ccodex sdlc``
    plane no gate ever ran).
  * The cases are ``policy/release-smoke.v1.json``, so adding one is a data edit that the same
    reader drives locally (``mise run release:smoke``) and in CI.  Unknown fields, unknown
    platforms, duplicate ids, and an empty selection are each refused by name; nothing is inferred
    from an absent key.
  * EVERY case asserts OUTPUT, never a bare exit code.  Exit 3 is a legitimate status here -- a
    refusal before any effect -- so only the report body distinguishes "refused because the host is
    not certified" from "refused because the dispatcher built the wrong interpreter invocation".
    A refusal case therefore carries ``expect_stderr_absent`` for the admission text as well as
    the refusal it expects, which is what makes it a direct negative for issue #9 rather than a
    case a broken dispatcher could satisfy by refusing for the wrong reason.
  * ``stdout`` carries reports and ``stderr`` carries refusals, and the two are never conflated:
    ``bin/ccodex`` documents that mise resolution noise and a global-config lockfile ``WARN`` land
    on stderr deliberately.
  * ``environment`` selects one of three: ``host`` inherits the invoking environment verbatim,
    ``toolfree`` runs with a PATH holding only base utilities, and ``scratch-state`` inherits the host
    but relocates HOME and every XDG root into the case's own directory while pinning mise's and uv's
    own directories back.  A case whose verdict depends on whether an operator plane is EMPTY belongs
    in ``scratch-state``: under ``host`` it is asserting a fact about the machine that ran it
    (agentic-sdlc-66ca).  Isolation alone is not proof of the reason -- a moved trust store makes the
    dispatcher refuse at the same exit code with a different body -- so such a case also forbids the
    trust text on stderr.
  * ``forbid_finding_codes`` names the report's own ``findings[].code`` vocabulary.  Issue #9's
    design sketch called the field ``forbid_finding_ids``; the report spells them ``code``, so
    this manifest does too.
  * ``--expect-refusal`` inverts the verdict for the mutation proof: the run is admitted only when
    at least one case FAILED, every ``--require-marker`` appears in some failing case's evidence,
    and every failing case is attributed to one of those markers.  An unrelated breakage therefore
    cannot satisfy the mutation job, and a mutation that stopped mattering cannot either.

WHAT THIS PROVES AND DOES NOT PROVE.  A passing run says the shipped dispatcher reaches its reader
on its own bound interpreter and that each observed stream matches the manifest.  It says nothing
about whether the report's CONTENT is correct beyond the fields asserted, and it is evidence only:
it authorizes no publication.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_REFUSED = 3

POLICY_RELATIVE = Path("policy") / "release-smoke.v1.json"
SCHEMA_VERSION = "release-smoke/v1"
TREE_TOKEN = "{tree}"
#: The exact operating systems this manifest may name.  Windows is deliberately absent: whether the
#: extracted ``bin/ccodex`` -- a bash script -- is even reachable on a Windows runner is unmeasured,
#: and a case that named it would claim coverage nobody observed (issue #9, "Windows: out of scope").
PLATFORMS = ("Darwin", "Linux")
ENVIRONMENTS = ("host", "scratch-state", "toolfree")
#: The base utilities the dispatcher's tool-free verbs may use.  A ``toolfree`` case runs with a
#: PATH holding only these, so passing genuinely proves no mise, uv, jq, or ocx was needed -- a
#: positive isolation rather than a stripped environment.
TOOLFREE_UTILITIES = ("bash", "cat", "dirname", "realpath")
#: The operator-plane roots a ``scratch-state`` case relocates into its own scratch directory, each
#: with the tail its XDG default appends to ``HOME``.  Both halves of the acquisition plane are here
#: on purpose: a receipt lives under ``XDG_STATE_HOME`` and the release root it would be sealed from
#: lives under ``XDG_DATA_HOME``, so isolating one and inheriting the other still lets host state
#: decide the verdict.
SCRATCH_STATE_ROOTS = (
    ("XDG_STATE_HOME", ("state",)),
    ("XDG_DATA_HOME", ("data",)),
    ("XDG_CONFIG_HOME", ("config",)),
    ("XDG_CACHE_HOME", ("cache",)),
)
#: What must be pinned BACK to the invoking host when those roots move, as (variable, XDG variable,
#: that variable's default tail under ``HOME``, the tool's own leaf).  mise keeps its trust store and
#: its installed toolchain under the operator's XDG roots, and uv keeps its cache and managed
#: interpreters there, so relocating the roots without these pins breaks the run in two ways that both
#: look like something else: mise reports the extracted tree's ``mise.toml`` as UNTRUSTED, so the
#: dispatcher refuses at exit 3 with a body about trust rather than about the verb under test, and
#: mise's install tree reads as absent, so ``auto_install`` downloads the whole pinned toolset inside
#: a smoke run.  An explicit value already in the environment is the operator's own pin and is kept.
TOOLCHAIN_PINS = (
    ("MISE_CONFIG_DIR", "XDG_CONFIG_HOME", (".config",), ("mise",)),
    ("MISE_DATA_DIR", "XDG_DATA_HOME", (".local", "share"), ("mise",)),
    ("MISE_STATE_DIR", "XDG_STATE_HOME", (".local", "state"), ("mise",)),
    ("MISE_CACHE_DIR", "XDG_CACHE_HOME", (".cache",), ("mise",)),
    ("UV_CACHE_DIR", "XDG_CACHE_HOME", (".cache",), ("uv",)),
    ("UV_PYTHON_INSTALL_DIR", "XDG_DATA_HOME", (".local", "share"), ("uv", "python")),
)
STRING_LIST_FIELDS = (
    "expect_stdout_present",
    "expect_stdout_absent",
    "expect_stdout_matches",
    "expect_stderr_present",
    "expect_stderr_absent",
    "forbid_finding_codes",
)
REQUIRED_FIELDS = ("id", "argv", "platforms", "environment", "expect_exit")
OPTIONAL_FIELDS = ("expect_stdout_json", *STRING_LIST_FIELDS)
#: How much of a failing case's captured stream reaches the log.  A gate whose evidence is elided
#: is a claim; a whole browser-sized stream would bury it.
STREAM_EXCERPT_BYTES = 4000


class Refusal(RuntimeError):
    pass


class Observation:
    def __init__(self, case: dict[str, Any], completed: subprocess.CompletedProcess[str] | None, timeout: bool):
        self.case = case
        self.timeout = timeout
        self.returncode = -1 if completed is None else completed.returncode
        self.stdout = "" if completed is None else completed.stdout
        self.stderr = "" if completed is None else completed.stderr

    @property
    def evidence(self) -> str:
        return f"{self.stdout}\n{self.stderr}"


def load_manifest(path: Path) -> list[dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"{path} is unreadable or not JSON: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"schema_version", "cases"}:
        raise Refusal(f"{path} must be an object carrying exactly schema_version and cases")
    if document["schema_version"] != SCHEMA_VERSION:
        raise Refusal(f"{path} declares schema {document['schema_version']!r}, not {SCHEMA_VERSION!r}")
    cases = document["cases"]
    if not isinstance(cases, list) or not cases:
        raise Refusal(f"{path} carries no cases")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        validate_case(case, f"{path} cases[{index}]")
        if case["id"] in seen:
            raise Refusal(f"{path} declares the case id {case['id']!r} twice")
        seen.add(case["id"])
    return cases


def validate_case(case: object, label: str) -> None:
    if not isinstance(case, dict):
        raise Refusal(f"{label} is not an object")
    unknown = set(case) - {*REQUIRED_FIELDS, *OPTIONAL_FIELDS}
    if unknown:
        raise Refusal(f"{label} carries unknown fields {sorted(unknown)}")
    missing = [field for field in REQUIRED_FIELDS if field not in case]
    if missing:
        raise Refusal(f"{label} is missing {missing}")
    if not isinstance(case["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["id"]):
        raise Refusal(f"{label} id must be a lowercase-hyphen slug")
    argv = case["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise Refusal(f"{label} argv must be a non-empty list of non-empty strings")
    platforms = case["platforms"]
    if (
        not isinstance(platforms, list)
        or not platforms
        or sorted(set(platforms)) != sorted(platforms)
        or any(name not in PLATFORMS for name in platforms)
    ):
        raise Refusal(f"{label} platforms must be a unique non-empty subset of {list(PLATFORMS)}")
    if case["environment"] not in ENVIRONMENTS:
        raise Refusal(f"{label} environment must be one of {list(ENVIRONMENTS)}")
    exit_code = case["expect_exit"]
    if isinstance(exit_code, bool) or not isinstance(exit_code, int) or not 0 <= exit_code <= 4:
        raise Refusal(f"{label} expect_exit must be an integer in the 0-4 exit class")
    for field in STRING_LIST_FIELDS:
        value = case.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise Refusal(f"{label} {field} must be a list of non-empty strings")
    for pattern in case.get("expect_stdout_matches", []):
        try:
            re.compile(pattern)
        except re.error as exc:
            raise Refusal(f"{label} expect_stdout_matches carries an invalid regex {pattern!r}: {exc}") from exc
    expected_json = case.get("expect_stdout_json", {})
    if not isinstance(expected_json, dict) or not all(
        isinstance(key, str) and key and not key.startswith(".") and not key.endswith(".")
        for key in expected_json
    ):
        raise Refusal(f"{label} expect_stdout_json must be an object keyed by dotted report paths")
    # An output assertion is the whole methodological point: a case that checked only its exit code
    # would have passed at v0.7.4 for three of the four verbs this manifest exists to gate.
    if not any(case.get(field) for field in (*STRING_LIST_FIELDS, "expect_stdout_json")):
        raise Refusal(f"{label} asserts only an exit code; every case must assert output")


def resolve_tree(tree: Path, checkout: Path) -> Path:
    resolved = Path(os.path.realpath(tree))
    if not resolved.is_dir():
        raise Refusal(f"--tree {tree} is not a directory; extract the release archive first")
    if resolved == checkout or checkout in resolved.parents:
        raise Refusal(
            f"--tree {resolved} sits inside this checkout ({checkout}); this gate must run the"
            " EXTRACTED archive's own bytes, so a tree under the repository is refused rather than"
            " smoke-tested as though it were the shipped artifact"
        )
    dispatcher = resolved / "bin" / "ccodex"
    if dispatcher.is_symlink() or not dispatcher.is_file():
        raise Refusal(f"{dispatcher} is absent or a symlink; that tree is not an extracted archive")
    if not os.access(dispatcher, os.X_OK):
        raise Refusal(f"{dispatcher} is not executable; the archive's mode did not survive extraction")
    return resolved


def toolfree_path(scratch: Path) -> str:
    directory = scratch / "toolfree-bin"
    directory.mkdir(exist_ok=True)
    for tool in TOOLFREE_UTILITIES:
        resolved = shutil.which(tool)
        if resolved and not (directory / tool).exists():
            os.symlink(resolved, directory / tool)
    return str(directory)


def host_default(xdg_variable: str, default_tail: tuple[str, ...]) -> Path:
    """Where the INVOKING host resolves one XDG root, whether or not it names it explicitly."""
    value = os.environ.get(xdg_variable)
    if value and value.strip():
        return Path(value)
    return Path(os.path.expanduser("~")).joinpath(*default_tail)


def scratch_state_environment(case: dict[str, Any], scratch: Path) -> dict[str, str]:
    """The host environment with every operator plane moved into this case's own directory.

    WHY THIS MODE EXISTS.  ``install-refuses-before-effect-on-linux`` asserts that the shipped
    dispatcher refuses because no acquired candidate is available, and under ``host`` that verdict was
    a fact about the invoking machine rather than about the artifact: the refusal holds only while the
    acquisition planes are empty.  On a host holding a sealed receipt, or a staged release root the
    installer would mint a ticket from, the same argv proceeds PAST that refusal and performs a real
    activation into the operator's own Claude home during a smoke run.  No such host exists today,
    which is exactly the shape of environmental luck this manifest has already been burned by twice
    (agentic-sdlc-66ca, and the terminal-line case before it).

    So the case gets its own HOME and its own XDG roots, and the toolchain that has to keep working
    across that move is pinned back BY ITS OWN VARIABLES rather than left to re-derive.  What this
    does NOT do is prove the refusal came from the right place -- an unpinned mise answers "not
    trusted" at the same exit code -- so the manifest case carries the trust text in
    ``expect_stderr_absent`` and the assertion lives there, where a reader can see it.
    """
    environment = dict(os.environ)
    base = scratch / "scratch-state" / case["id"]
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    for variable, xdg_variable, default_tail, leaf in TOOLCHAIN_PINS:
        if not environment.get(variable, "").strip():
            environment[variable] = str(host_default(xdg_variable, default_tail).joinpath(*leaf))
    environment["HOME"] = str(home)
    for variable, tail in SCRATCH_STATE_ROOTS:
        root = base.joinpath(*tail)
        root.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(root)
    return environment


def case_environment(case: dict[str, Any], scratch: Path) -> dict[str, str]:
    if case["environment"] == "host":
        return dict(os.environ)
    if case["environment"] == "scratch-state":
        return scratch_state_environment(case, scratch)
    # An allowlist, not os.environ minus a blocklist: HOME is the only other value the tool-free
    # verbs may read, and inheriting more would let an ambient tool root re-enter the PATH.
    return {"PATH": toolfree_path(scratch), "HOME": os.environ.get("HOME", str(scratch))}


def run_case(case: dict[str, Any], tree: Path, scratch: Path, timeout: int) -> Observation:
    # cwd is a scratch directory outside the tree, so nothing under test may depend on being run
    # from its own root.
    working = scratch / "cwd"
    working.mkdir(exist_ok=True)
    try:
        completed = subprocess.run(
            [str(tree / "bin" / "ccodex"), *case["argv"]],
            env=case_environment(case, scratch),
            cwd=str(working),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Observation(case, None, timeout=True)
    return Observation(case, completed, timeout=False)


def dotted(document: Any, path: str) -> tuple[bool, Any]:
    current = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def same(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(observed, bool):
        return isinstance(observed, bool) and isinstance(expected, bool) and observed == expected
    return observed == expected


def assess(observation: Observation, tree: Path) -> list[str]:
    """Every mismatch this case shows, so one run reports all of them rather than the first."""
    case = observation.case
    failures: list[str] = []
    if observation.timeout:
        return ["the invocation did not finish within the timeout"]
    if observation.returncode != case["expect_exit"]:
        failures.append(f"exit {observation.returncode}, expected {case['expect_exit']}")

    def expand(value: str) -> str:
        return value.replace(TREE_TOKEN, str(tree))

    for needle in case.get("expect_stdout_present", []):
        if expand(needle) not in observation.stdout:
            failures.append(f"stdout is missing {expand(needle)!r}")
    for needle in case.get("expect_stdout_absent", []):
        if expand(needle) in observation.stdout:
            failures.append(f"stdout carries the forbidden {expand(needle)!r}")
    for pattern in case.get("expect_stdout_matches", []):
        if not re.search(pattern, observation.stdout):
            failures.append(f"stdout matches no {pattern!r}")
    for needle in case.get("expect_stderr_present", []):
        if expand(needle) not in observation.stderr:
            failures.append(f"stderr is missing {expand(needle)!r}")
    for needle in case.get("expect_stderr_absent", []):
        if expand(needle) in observation.stderr:
            failures.append(f"stderr carries the forbidden {expand(needle)!r}")

    expected_json = case.get("expect_stdout_json", {})
    forbidden = case.get("forbid_finding_codes", [])
    if expected_json or forbidden:
        try:
            report = json.loads(observation.stdout)
        except json.JSONDecodeError as exc:
            failures.append(f"stdout is not the JSON report this case asserts on: {exc}")
            return failures
        if not isinstance(report, dict):
            failures.append("stdout is JSON but not an object")
            return failures
        for path, expected in sorted(expected_json.items()):
            found, observed = dotted(report, path)
            if not found:
                failures.append(f"the report carries no {path}")
            elif not same(observed, expected):
                failures.append(f"report {path} is {observed!r}, expected {expected!r}")
        codes = {
            finding.get("code")
            for finding in report.get("findings", [])
            if isinstance(finding, dict)
        }
        for code in forbidden:
            if code in codes:
                failures.append(f"the report carries the forbidden finding code {code!r}")
    return failures


def excerpt(stream: str) -> str:
    if len(stream) <= STREAM_EXCERPT_BYTES:
        return stream
    return f"{stream[:STREAM_EXCERPT_BYTES]}\n[...{len(stream) - STREAM_EXCERPT_BYTES} more characters]"


def report_case(identifier: str, failures: list[str], observation: Observation) -> None:
    if not failures:
        print(f"pass {identifier}")
        return
    print(f"FAIL {identifier}")
    for failure in failures:
        print(f"     {failure}")
    print(f"     argv: {' '.join(observation.case['argv'])}")
    print(f"     exit: {observation.returncode}")
    for name, stream in (("stdout", observation.stdout), ("stderr", observation.stderr)):
        if stream.strip():
            print(f"     --- {name} ---")
            for line in excerpt(stream).splitlines():
                print(f"     {line}")


def verdict_expect_refusal(
    failed: list[tuple[str, list[str], Observation]], markers: list[str]
) -> tuple[int, list[str]]:
    """Admit the mutation proof only when the smoke failed FOR THE NAMED REASONS."""
    lines: list[str] = []
    if not failed:
        lines.append(
            "refusal expected: every case passed, so the mutation under test no longer changes"
            " observable behavior and this gate has stopped proving anything"
        )
        return EXIT_FAILED, lines
    unattributed = [
        identifier
        for identifier, _failures, observation in failed
        if not any(marker in observation.evidence for marker in markers)
    ]
    unseen = [
        marker
        for marker in markers
        if not any(marker in observation.evidence for _identifier, _failures, observation in failed)
    ]
    for marker in markers:
        witnesses = [
            identifier
            for identifier, _failures, observation in failed
            if marker in observation.evidence
        ]
        lines.append(f"marker {marker!r}: {'named by ' + ', '.join(witnesses) if witnesses else 'NEVER OBSERVED'}")
    if unseen:
        lines.append(f"required markers never observed: {unseen}")
    if unattributed:
        lines.append(
            f"cases failed for an unrelated reason: {unattributed}; a mutation gate satisfied by an"
            " unrelated breakage is not evidence"
        )
    if unseen or unattributed:
        return EXIT_FAILED, lines
    lines.append(
        f"refusal proven: {len(failed)} case(s) failed and every failure is attributed to a required marker"
    )
    return EXIT_OK, lines


def main(argv: list[str] | None = None) -> int:
    checkout = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run the release smoke manifest against an extracted archive")
    parser.add_argument("--tree", type=Path, required=True, help="the EXTRACTED archive root to execute")
    parser.add_argument("--policy", type=Path, default=checkout / POLICY_RELATIVE)
    parser.add_argument("--case", action="append", default=[], help="run only this case id (repeatable)")
    parser.add_argument("--timeout", type=int, default=600, help="per-case timeout in seconds")
    parser.add_argument(
        "--expect-refusal",
        action="store_true",
        help="invert the verdict: the run is admitted only when it FAILS for a required marker",
    )
    parser.add_argument(
        "--require-marker",
        action="append",
        default=[],
        help="with --expect-refusal, a string every failure must be attributable to (repeatable)",
    )
    arguments = parser.parse_args(argv)
    if arguments.require_marker and not arguments.expect_refusal:
        print("error: --require-marker is meaningful only with --expect-refusal", file=sys.stderr)
        return EXIT_USAGE
    if arguments.expect_refusal and not arguments.require_marker:
        print(
            "error: --expect-refusal requires at least one --require-marker, so a failure for an"
            " unrelated reason cannot satisfy the mutation proof",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if arguments.timeout <= 0:
        print("error: --timeout must be a positive number of seconds", file=sys.stderr)
        return EXIT_USAGE

    system = platform.system()
    try:
        cases = load_manifest(arguments.policy)
        tree = resolve_tree(arguments.tree, checkout)
        known = {case["id"] for case in cases}
        unknown = sorted(set(arguments.case) - known)
        if unknown:
            raise Refusal(f"--case names no such case: {unknown}")
        selected = [
            case
            for case in cases
            if system in case["platforms"] and (not arguments.case or case["id"] in arguments.case)
        ]
        if not selected:
            raise Refusal(f"no case in {arguments.policy} is declared for {system}")
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED

    print(f"smoke {arguments.policy.name} on {system}")
    print(f"tree  {tree}")
    failed: list[tuple[str, list[str], Observation]] = []
    with tempfile.TemporaryDirectory(prefix="release-smoke-") as temporary:
        scratch = Path(temporary)
        for case in selected:
            observation = run_case(case, tree, scratch, arguments.timeout)
            failures = assess(observation, tree)
            report_case(case["id"], failures, observation)
            if failures:
                failed.append((case["id"], failures, observation))

    print(f"{len(selected)} selected, {len(selected) - len(failed)} passed, {len(failed)} failed on {system}")
    if arguments.expect_refusal:
        status, lines = verdict_expect_refusal(failed, arguments.require_marker)
        for line in lines:
            print(line)
        return status
    return EXIT_FAILED if failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
