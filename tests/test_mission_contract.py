"""Tests for the MissionContract definer and its digest.

Four kinds of test live here and they check different things.

The ROUND-TRIP tests seal a body with `define`, then hand the sealed document straight back to
`verify`, so the two commands are proved to agree about the one digest rather than each being proved
against a constant this module chose. `verify --expect-digest` closes the loop a downstream
consumer will actually use.

The NEGATIVE cases each carry a POSITIVE CONTROL in the same test: the unmutated body is asserted to
reach `defined` (or the unmutated sealed document `verified`) FIRST, so a test that stopped
exercising its guard would also have to stop reaching that verdict. Several of them mutate a document
this module's own `define` produced, which is the only way to reach a shape the tool will not emit.

The CANONICAL-FORM tests assert BYTES, not parsed values, and one of them carries a non-ASCII
objective, because `ensure_ascii=True` is the half of the canonical form that a JSON round-trip
cannot detect.

The HOSTILE-DESCRIPTOR cases run the tool with a stderr or a stdout it cannot write to -- `2>&-`
and a real pipe whose reader is already gone -- because a display channel must cost the display line
and never the classified exit code, and because the one result document is the evidence: a contract
sealed and not delivered is not a success.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "mission-contract.py"
#: Used only as the POSITIVE CONTROL for `test_the_tool_reads_no_environment_variable`.
JOURNAL_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-journal.py"

CONTRACT_SCHEMA = "agentic-sdlc/mission-contract@1"
RESULT_SCHEMA = "agentic-sdlc/mission-contract-result@1"

DEFINED = "defined"
VERIFIED = "verified"
REFUSED = "refused"

EXIT_OK = 0
#: The undelivered-document code. A result this tool derived but could not put on stdout is neither a
#: success nor an input error, and 120 is not in the module's exit space at all.
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The authority ladder, ascending, exactly as the tool declares it.
LADDER = ("read-only-advisory", "owned-worktree-write", "authorized-fan-in", "outward-effect")

#: The four stop conditions no contract may omit.
MANDATORY_STOPS = (
    "authority-expansion-required",
    "hard-stop-drift",
    "scope-change-required",
    "unknown-or-partial-effect",
)
OPTIONAL_STOPS = (
    "approval-invalid-or-expired",
    "budget-exhausted",
    "capability-unsupported",
    "contradictory-or-missing-evidence",
    "custody-conflict",
    "unresolved-runtime-assignment",
)

#: Every refusal must name one of these. Nested keys are included because a nested mistake must be
#: named at the level the caller wrote it, not as "scope is wrong".
FIELD_NAMES = (
    "schema",
    "mission_id",
    "objective",
    "scope",
    "in_scope",
    "non_goals",
    "constraints",
    "authority",
    "admitted_classes",
    "ceiling",
    "completion_contract",
    "success_criteria",
    "terminal_criteria",
    "stop_conditions",
    "stated_at",
    "revision",
    "supersedes",
    "digest",
)

T0 = "2026-08-19T02:00:00Z"
T1 = "2026-08-19T02:01:00Z"

MISSION_ID = "mission-slice-6"

#: The tool reads no environment variable at all, so nothing needs scrubbing by name; every spawn
#: still CONSTRUCTS its environment from this function rather than passing `os.environ` through, so a
#: variable a future version began reading could not silently reach it from a developer's shell.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every spawn in this module hands the tool: an ALLOWLIST, not an inheritance.

    Only what a usable interpreter needs is carried across. `test_the_tool_reads_no_environment_
    variable` is the assertion that this set is sufficient; a tool that grew a control variable would
    not find it here.
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


def run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Two shapes, kept separate because they produce DIFFERENT wrong exit codes and neither is exotic:

        closed  `2>&-`. CPython then starts with `sys.stderr is None`, so the FIRST
                `sys.stderr.write` raises `AttributeError` and the classified code becomes 1.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write raises
                EPIPE and leaves bytes pending that CPython flushes again while finalizing, which
                replaces the exit code with 120.

    Stderr is deliberately NOT captured: capturing it would hand the child a writable stream and
    test nothing.
    """
    if mode == "closed":
        done = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
            env=constructed_environment(),
        )
        return done.returncode, done.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd), env=constructed_environment()
        )
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def run_with_hostile_stdout(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stdout this process CANNOT write to. Returns (exit code, stderr bytes).

    The mirror of `run_with_hostile_stderr`, and a DIFFERENT contract: stdout carries the one result
    document, so the tool may not deliver it and may not pretend it did.
    """
    if mode == "closed":
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&-; exec "$@"', "sh", *argv],
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
            env=constructed_environment(),
        )
        return done.returncode, done.stderr
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stdout mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        child = subprocess.Popen(
            argv, stdout=write_fd, stderr=subprocess.PIPE, cwd=str(cwd), env=constructed_environment()
        )
    finally:
        os.close(write_fd)
    assert child.stderr is not None
    with child.stderr as stream:
        err = stream.read()
    return child.wait(), err


def imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    """The module's top-level import names and every called name, read with `ast`.

    A substring search would be fooled by prose: this tool's own docstring contains the word
    "subprocess-free", and a `assertNotIn("subprocess", source)` would fail on the promise itself.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return modules, calls


def contract_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid MissionContract body: the positive control every negative case starts from.

    `admitted_classes` is a two-rung LADDER PREFIX and `stop_conditions` is a lexicographically
    sorted SET, because those are the two canonical forms the tool requires and this fixture must be
    in them to be a control.
    """
    body: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "mission_id": MISSION_ID,
        "objective": "close slice 6 by defining the planning artifact chain's first link",
        "scope": {
            "in_scope": ["skills/agentic-sdlc/tools/mission-contract.py", "tests/test_mission_contract.py"],
            "non_goals": ["the wave-plan compiler", "the plan admission gate"],
        },
        "constraints": [
            "read-only, offline, and subprocess-free",
            "no clock: every instant is a caller-supplied input",
        ],
        "authority": {
            "admitted_classes": ["read-only-advisory", "owned-worktree-write"],
            "ceiling": "owned-worktree-write",
        },
        "completion_contract": {
            "success_criteria": ["the digest re-derives from the sealed document"],
            "terminal_criteria": ["one named refusal for every malformed contract"],
        },
        "stop_conditions": sorted(MANDATORY_STOPS),
        "stated_at": T0,
        "revision": 1,
        "supersedes": None,
    }
    body.update(overrides)
    return body


class ContractCase(unittest.TestCase):
    """Seals bodies and verifies sealed documents, each in its own constructed scratch directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name).resolve()

    # ---- plumbing -------------------------------------------------------------------------------

    def store(self, name: str, value: Any) -> Path:
        """Write one document to scratch. `indent=2` deliberately: the input's whitespace must not
        reach the digest, and a pretty-printed input is the cheapest proof of that."""
        path = self.work / f"{name}.json"
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def store_bytes(self, name: str, raw: bytes) -> Path:
        path = self.work / f"{name}.json"
        path.write_bytes(raw)
        return path

    def run_tool(self, *argv: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", str(TOOL), *argv],
            capture_output=True,
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )

    def define(self, body: dict[str, Any], *extra: str, name: str = "body") -> dict[str, Any]:
        done = self.run_tool("define", "--contract", str(self.store(name, body)), *extra)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return json.loads(done.stdout)

    def verify(self, sealed: dict[str, Any], *extra: str, name: str = "sealed") -> dict[str, Any]:
        done = self.run_tool("verify", "--contract", str(self.store(name, sealed)), *extra)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return json.loads(done.stdout)

    def sealed_control(self) -> dict[str, Any]:
        """The sealed document every `verify` negative case mutates, asserted good on the way out."""
        document = self.define(contract_body())
        self.assertEqual(document["verdict"], DEFINED)
        contract = document["contract"]
        assert isinstance(contract, dict)
        return contract

    def assert_refused(self, document: dict[str, Any], needle: str) -> None:
        self.assertEqual(document["verdict"], REFUSED, document["reasons"])
        self.assertIsNone(document["contract"])
        joined = " | ".join(document["reasons"])
        self.assertIn(needle, joined)
        for reason in document["reasons"]:
            # Every refusal NAMES a field and says what was wrong with it, so a bare "invalid
            # contract" is unreachable. The check is the positive property rather than a banned word:
            # one of the schema's own field names must appear in the sentence.
            self.assertTrue(
                any(field in reason for field in FIELD_NAMES),
                f"a refusal that names no field is useless to the human it asks: {reason}",
            )
            self.assertGreater(len(reason), 30, reason)


class RoundTripTests(ContractCase):
    """A valid contract seals, its digest re-derives, and the two commands agree about it."""

    def test_a_valid_contract_seals_and_its_digest_re_derives(self) -> None:
        document = self.define(contract_body())
        self.assertEqual(document["schema"], RESULT_SCHEMA)
        self.assertEqual(document["command"], "define")
        self.assertEqual(document["verdict"], DEFINED)
        self.assertEqual(document["reasons"], [])
        contract = document["contract"]
        self.assertEqual(sorted(contract), sorted(list(contract_body()) + ["digest"]))
        self.assertEqual(contract["digest"], expected_digest(contract))
        self.assertEqual(document["digest"], contract["digest"])
        self.assertEqual(document["mission_id"], MISSION_ID)
        self.assertEqual(document["authority_ceiling"], "owned-worktree-write")

    def test_the_sealed_document_verifies_and_both_commands_agree_on_the_digest(self) -> None:
        sealed = self.sealed_control()
        document = self.verify(sealed)
        self.assertEqual(document["verdict"], VERIFIED)
        self.assertEqual(document["command"], "verify")
        self.assertEqual(document["digest"], sealed["digest"])
        self.assertEqual(document["contract"], sealed)

    def test_verify_binds_an_expected_digest_the_way_a_downstream_consumer_will(self) -> None:
        sealed = self.sealed_control()
        # POSITIVE CONTROL: the right digest verifies through the same option.
        self.assertEqual(self.verify(sealed, "--expect-digest", sealed["digest"])["verdict"], VERIFIED)
        other = "0" * 64
        self.assert_refused(self.verify(sealed, "--expect-digest", other), "--expect-digest")

    def test_input_whitespace_does_not_reach_the_digest(self) -> None:
        body = contract_body()
        first = self.define(body, name="pretty")["digest"]
        packed = self.work / "packed.json"
        packed.write_bytes(json.dumps(body, separators=(",", ":")).encode("utf-8"))
        done = self.run_tool("define", "--contract", str(packed))
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(json.loads(done.stdout)["digest"], first)

    def test_a_key_reordered_in_the_input_does_not_change_the_digest(self) -> None:
        body = contract_body()
        reversed_body = {key: body[key] for key in reversed(list(body))}
        self.assertNotEqual(list(reversed_body), list(body))  # POSITIVE CONTROL: the input differs
        self.assertEqual(self.define(body, name="a")["digest"], self.define(reversed_body, name="b")["digest"])

    def test_a_changed_field_changes_the_digest(self) -> None:
        """The other half of stability: a digest that ignored content would pass every test above."""
        first = self.define(contract_body(), name="a")["digest"]
        second = self.define(contract_body(objective="a different durable objective"), name="b")["digest"]
        self.assertNotEqual(first, second)


class RequiredFieldTests(ContractCase):
    """Every one of the closed body's keys is required, and each absence is refused BY NAME."""

    def test_every_required_field_missing_refuses_by_its_own_name(self) -> None:
        keys = sorted(contract_body())
        self.assertEqual(len(keys), 11, "the closed body key set changed; update this test deliberately")
        for key in keys:
            with self.subTest(missing=key):
                # POSITIVE CONTROL: the same body WITH the field seals.
                self.assertEqual(self.define(contract_body(), name=f"control-{key}")["verdict"], DEFINED)
                body = contract_body()
                del body[key]
                document = self.define(body, name=f"missing-{key}")
                self.assert_refused(document, f"carries no {key}")

    def test_an_unknown_field_refuses_rather_than_being_ignored(self) -> None:
        # POSITIVE CONTROL: without the extra key the same body seals.
        self.assertEqual(self.define(contract_body(), name="control")["verdict"], DEFINED)
        document = self.define(contract_body(auto_envelope={"enabled": True}), name="extra")
        self.assert_refused(document, "auto_envelope")

    def test_a_define_body_that_already_carries_a_digest_refuses(self) -> None:
        """The digest is DERIVED, never supplied: accepting one would be a second way to compute it."""
        sealed = self.sealed_control()
        document = self.define(sealed, name="presealed")
        # The precise needle: refused BECAUSE the digest is derived, not merely swept up by the
        # generic unknown-field reason, which would tell the caller to delete the field rather than
        # that supplying it is what gives the one load-bearing value a second origin.
        self.assert_refused(document, "never supplied")

    def test_a_verify_document_carrying_no_digest_refuses(self) -> None:
        # POSITIVE CONTROL: the sealed document, which does carry one, verifies.
        self.assertEqual(self.verify(self.sealed_control())["verdict"], VERIFIED)
        document = self.verify(contract_body(), name="unsealed")
        self.assert_refused(document, "carries no digest")

    def test_a_wrong_schema_tag_refuses(self) -> None:
        document = self.define(contract_body(schema="agentic-sdlc/mission-contract@2"), name="v2")
        self.assert_refused(document, "schema")

    def test_a_nested_object_with_an_unknown_key_refuses(self) -> None:
        body = contract_body(scope={"in_scope": ["a"], "non_goals": ["b"], "maybe": ["c"]})
        self.assert_refused(self.define(body, name="nested"), "maybe")

    def test_an_empty_string_in_a_prose_list_refuses(self) -> None:
        self.assert_refused(self.define(contract_body(constraints=["ok", ""]), name="blank"), "constraints")

    def test_an_empty_prose_list_refuses(self) -> None:
        self.assert_refused(self.define(contract_body(constraints=[]), name="empty"), "constraints")

    def test_an_empty_or_mistyped_text_field_refuses(self) -> None:
        for key in ("mission_id", "objective"):
            for value in ("", 7, None, ["a"]):
                with self.subTest(field=key, value=value):
                    document = self.define(contract_body(**{key: value}), name=f"text-{key}")
                    self.assert_refused(document, f"{key} is not a non-empty string")

    def test_a_nested_object_missing_a_key_refuses(self) -> None:
        self.assert_refused(self.define(contract_body(scope={"in_scope": ["a"]}), name="half"), "carries no non_goals")

    def test_a_nested_object_that_is_not_an_object_refuses(self) -> None:
        # A list is the interesting wrong type: `set(a_list)` succeeds, so without the type guard the
        # keys would be looked for among the list's OWN entries and refused as "carries no ceiling",
        # which names the wrong mistake.
        self.assert_refused(
            self.define(contract_body(authority=["read-only-advisory"]), name="list"), "is not a JSON object"
        )


class AuthorityLadderTests(ContractCase):
    """`admitted_classes` is a contiguous ladder prefix and `ceiling` is re-derived from it."""

    def test_an_out_of_vocabulary_authority_class_refuses(self) -> None:
        # POSITIVE CONTROL: the in-vocabulary two-rung prefix seals.
        self.assertEqual(self.define(contract_body(), name="control")["verdict"], DEFINED)
        body = contract_body(
            authority={"admitted_classes": ["read-only-advisory", "sudo-everything"], "ceiling": "sudo-everything"}
        )
        self.assert_refused(self.define(body, name="bogus"), "sudo-everything")

    def test_an_out_of_vocabulary_authority_class_with_a_valid_ceiling_refuses(self) -> None:
        """The case above also gives a bogus CEILING, which the ceiling-shape guard alone would also
        catch. A valid ceiling here isolates the vocabulary guard as the only guard that can catch an
        out-of-vocabulary entry in admitted_classes."""
        # POSITIVE CONTROL: the same body with only in-vocabulary classes seals.
        control = contract_body(
            authority={"admitted_classes": ["read-only-advisory"], "ceiling": "read-only-advisory"}
        )
        self.assertEqual(self.define(control, name="control")["verdict"], DEFINED)
        body = contract_body(
            authority={
                "admitted_classes": ["read-only-advisory", "sudo-everything"],
                "ceiling": "read-only-advisory",
            }
        )
        self.assert_refused(self.define(body, name="bogus-valid-ceiling"), "sudo-everything")

    def test_every_ladder_prefix_seals_and_derives_its_own_ceiling(self) -> None:
        for length in range(1, len(LADDER) + 1):
            with self.subTest(rungs=length):
                prefix = list(LADDER[:length])
                body = contract_body(authority={"admitted_classes": prefix, "ceiling": prefix[-1]})
                document = self.define(body, name=f"prefix-{length}")
                self.assertEqual(document["verdict"], DEFINED, document["reasons"])
                self.assertEqual(document["authority_ceiling"], prefix[-1])

    def test_a_non_contiguous_prefix_refuses(self) -> None:
        body = contract_body(
            authority={"admitted_classes": ["read-only-advisory", "authorized-fan-in"], "ceiling": "authorized-fan-in"}
        )
        self.assert_refused(self.define(body, name="gap"), "contiguous")

    def test_a_prefix_that_does_not_start_at_the_lowest_rung_refuses(self) -> None:
        body = contract_body(
            authority={"admitted_classes": ["owned-worktree-write"], "ceiling": "owned-worktree-write"}
        )
        self.assert_refused(self.define(body, name="high"), "contiguous")

    def test_classes_out_of_ladder_order_refuse(self) -> None:
        body = contract_body(
            authority={
                "admitted_classes": ["owned-worktree-write", "read-only-advisory"],
                "ceiling": "owned-worktree-write",
            }
        )
        self.assert_refused(self.define(body, name="unordered"), "ladder order")

    def test_a_duplicate_authority_class_refuses(self) -> None:
        body = contract_body(
            authority={
                "admitted_classes": ["read-only-advisory", "read-only-advisory"],
                "ceiling": "read-only-advisory",
            }
        )
        self.assert_refused(self.define(body, name="dupe"), "ladder order")

    def test_a_stated_ceiling_the_admitted_classes_do_not_derive_refuses(self) -> None:
        body = contract_body(
            authority={"admitted_classes": ["read-only-advisory"], "ceiling": "outward-effect"}
        )
        self.assert_refused(self.define(body, name="ceiling"), "ceiling")

    def test_an_empty_admitted_class_list_refuses(self) -> None:
        body = contract_body(authority={"admitted_classes": [], "ceiling": "read-only-advisory"})
        self.assert_refused(self.define(body, name="none"), "admitted_classes")


class StopConditionTests(ContractCase):
    """`stop_conditions` is a closed, sorted, deduplicated set with a mandatory floor."""

    def test_an_out_of_vocabulary_stop_condition_refuses(self) -> None:
        # POSITIVE CONTROL: the in-vocabulary mandatory floor seals.
        self.assertEqual(self.define(contract_body(), name="control")["verdict"], DEFINED)
        body = contract_body(stop_conditions=sorted([*MANDATORY_STOPS, "when-the-agent-feels-done"]))
        self.assert_refused(self.define(body, name="bogus"), "when-the-agent-feels-done")

    def test_every_mandatory_stop_condition_omitted_refuses_by_name(self) -> None:
        for omitted in MANDATORY_STOPS:
            with self.subTest(omitted=omitted):
                remaining = sorted(set(MANDATORY_STOPS) - {omitted})
                document = self.define(contract_body(stop_conditions=remaining), name=f"drop-{omitted}")
                self.assert_refused(document, omitted)

    def test_every_optional_stop_condition_is_admitted(self) -> None:
        body = contract_body(stop_conditions=sorted([*MANDATORY_STOPS, *OPTIONAL_STOPS]))
        document = self.define(body, name="all")
        self.assertEqual(document["verdict"], DEFINED, document["reasons"])
        self.assertEqual(document["stop_conditions"], sorted([*MANDATORY_STOPS, *OPTIONAL_STOPS]))

    def test_an_unsorted_stop_condition_list_refuses(self) -> None:
        body = contract_body(stop_conditions=list(reversed(sorted(MANDATORY_STOPS))))
        self.assert_refused(self.define(body, name="unsorted"), "sorted")

    def test_a_duplicated_stop_condition_refuses(self) -> None:
        body = contract_body(stop_conditions=sorted([*MANDATORY_STOPS, MANDATORY_STOPS[0]]))
        self.assert_refused(self.define(body, name="dupe"), "sorted")


class DigestDisagreementTests(ContractCase):
    """A recorded digest that its own content does not derive is a NAMED refusal, not a warning."""

    def test_a_document_whose_recorded_digest_disagrees_with_its_content_refuses(self) -> None:
        sealed = self.sealed_control()
        # POSITIVE CONTROL: untouched, it verifies.
        self.assertEqual(self.verify(sealed, name="control")["verdict"], VERIFIED)
        edited = dict(sealed, objective="a quietly rewritten objective")
        document = self.verify(edited, name="edited")
        self.assert_refused(document, "does not re-derive")

    def test_a_rewritten_digest_field_refuses(self) -> None:
        sealed = self.sealed_control()
        document = self.verify(dict(sealed, digest="f" * 64), name="forged")
        self.assert_refused(document, "does not re-derive")

    def test_a_digest_that_is_not_64_lowercase_hex_refuses(self) -> None:
        sealed = self.sealed_control()
        for bad in ("F" * 64, "abc", "g" * 64, 12345):
            with self.subTest(digest=bad):
                document = self.verify(dict(sealed, digest=bad), name="shape")
                # The precise needle: a digest that is not a sha256 at all is refused for its SHAPE,
                # not merely swept up by the re-derivation mismatch that would also fire on any
                # 64-hex string. Those are two different guards and the caller is told which.
                self.assert_refused(document, "64 lowercase hexadecimal")

    def test_a_refused_document_carries_no_sealed_contract_and_no_digest(self) -> None:
        """An illegal contract is unrepresentable in the emitted document, not merely warned about."""
        document = self.define(contract_body(constraints=[]), name="bad")
        self.assertEqual(document["verdict"], REFUSED)
        self.assertIsNone(document["contract"])
        self.assertIsNone(document["digest"])
        # Nor is any admitted-looking field of a refused contract republished, so no consumer can
        # read a partially admitted contract out of a refusal.
        for key in ("mission_id", "authority_ceiling", "stop_conditions", "revision", "supersedes"):
            self.assertIsNone(document[key], key)
        # POSITIVE CONTROL: on the same fields, an admitted contract DOES publish values, so these
        # are assertions about the refusal and not about fields that are always null.
        admitted = self.define(contract_body(), name="good")
        for key in ("mission_id", "authority_ceiling", "stop_conditions", "revision"):
            self.assertIsNotNone(admitted[key], key)


class RevisionChainTests(ContractCase):
    """No clock: `stated_at` is caller-supplied, so a non-monotonic chain is refused by name."""

    def second_revision(self, prior: dict[str, Any], **overrides: Any) -> dict[str, Any]:
        body = contract_body(revision=2, supersedes=prior["digest"], stated_at=T1)
        body.update(overrides)
        return body

    def test_a_second_revision_seals_against_its_predecessor(self) -> None:
        prior = self.sealed_control()
        prior_path = self.store("prior", prior)
        document = self.define(self.second_revision(prior), "--supersedes", str(prior_path), name="next")
        self.assertEqual(document["verdict"], DEFINED, document["reasons"])
        self.assertNotEqual(document["digest"], prior["digest"])

    def test_a_revision_stamped_before_its_predecessor_refuses(self) -> None:
        prior = self.sealed_control()
        prior_path = self.store("prior", prior)
        # POSITIVE CONTROL: the same chain with a later instant seals.
        self.assertEqual(
            self.define(self.second_revision(prior), "--supersedes", str(prior_path), name="ok")["verdict"],
            DEFINED,
        )
        body = self.second_revision(prior, stated_at="2026-08-19T01:59:00Z")
        document = self.define(body, "--supersedes", str(prior_path), name="backwards")
        self.assert_refused(document, "stated_at")

    def test_a_revision_that_does_not_follow_its_predecessor_refuses(self) -> None:
        prior = self.sealed_control()
        prior_path = self.store("prior", prior)
        body = self.second_revision(prior, revision=7)
        self.assert_refused(self.define(body, "--supersedes", str(prior_path), name="skip"), "revision")

    def test_a_supersedes_digest_that_is_not_the_predecessors_refuses(self) -> None:
        prior = self.sealed_control()
        prior_path = self.store("prior", prior)
        body = self.second_revision(prior, supersedes="b" * 64)
        self.assert_refused(self.define(body, "--supersedes", str(prior_path), name="wrong"), "supersedes")

    def test_a_revision_naming_another_mission_refuses(self) -> None:
        prior = self.sealed_control()
        prior_path = self.store("prior", prior)
        body = self.second_revision(prior, mission_id="mission-other")
        self.assert_refused(self.define(body, "--supersedes", str(prior_path), name="other"), "mission_id")

    def test_a_later_revision_with_no_predecessor_supplied_refuses(self) -> None:
        prior = self.sealed_control()
        body = self.second_revision(prior)
        self.assert_refused(self.define(body, name="orphan"), "--supersedes")

    def test_a_first_revision_that_supersedes_something_refuses(self) -> None:
        body = contract_body(supersedes="c" * 64)
        self.assert_refused(self.define(body, name="rev1"), "supersedes")

    def test_a_first_revision_handed_a_predecessor_refuses(self) -> None:
        prior = self.sealed_control()
        prior_path = self.store("prior", prior)
        document = self.define(contract_body(), "--supersedes", str(prior_path), name="rev1")
        # The precise needle: refused for HAVING a predecessor, not swept up by the follows-check.
        self.assert_refused(document, "a predecessor was supplied")

    def test_a_predecessor_that_does_not_re_derive_its_own_digest_refuses(self) -> None:
        prior = self.sealed_control()
        # POSITIVE CONTROL: the untouched predecessor accepts the same second revision.
        good = self.store("good-prior", prior)
        self.assertEqual(
            self.define(self.second_revision(prior), "--supersedes", str(good), name="ok")["verdict"], DEFINED
        )
        edited = self.store("bad-prior", dict(prior, objective="rewritten after sealing"))
        document = self.define(self.second_revision(prior), "--supersedes", str(edited), name="chain")
        self.assert_refused(document, "does not re-derive its own digest")

    def test_a_revision_that_is_not_a_positive_integer_refuses(self) -> None:
        for bad in (0, -1, True, 1.0, "1"):
            with self.subTest(revision=bad):
                # The precise needle: `True` and `0` must be refused for the revision's own type and
                # range, not swept up by a downstream reason that merely mentions the word.
                self.assert_refused(
                    self.define(contract_body(revision=bad), name="rev"), "not an integer of at least 1"
                )

    def test_a_stated_at_that_is_not_a_fixed_width_instant_refuses(self) -> None:
        for bad in ("2026-08-19", "2026-08-19T02:00:00.000Z", "2026-08-19 02:00:00Z", 1755561600):
            with self.subTest(stated_at=bad):
                self.assert_refused(self.define(contract_body(stated_at=bad), name="when"), "stated_at")

    def test_a_stated_at_spelled_in_arabic_indic_digits_refuses(self) -> None:
        """`\\d` matches any Unicode decimal digit, not only ASCII 0-9, so an admitted Arabic-Indic
        stated_at would sort ABOVE every ASCII instant and silently defeat the monotonicity guard."""
        ascii_instant = "2020-08-19T02:00:00Z"
        # POSITIVE CONTROL: the same instant spelled in ASCII digits is admitted.
        self.assertEqual(self.define(contract_body(stated_at=ascii_instant), name="ascii")["verdict"], DEFINED)
        arabic_indic_instant = "٢٠٢٠-٠٨-١٩T٠٢:٠٠:٠٠Z"
        document = self.define(contract_body(stated_at=arabic_indic_instant), name="arabic-indic")
        self.assert_refused(document, "stated_at")


class CanonicalFormTests(ContractCase):
    """The emitted bytes, asserted as BYTES. A parsed round-trip cannot see any of this."""

    def test_the_result_document_is_canonical_bytes_with_one_trailing_newline(self) -> None:
        done = self.run_tool("define", "--contract", str(self.store("body", contract_body())))
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)))
        self.assertTrue(done.stdout.endswith(b"}\n"))
        self.assertEqual(done.stdout.count(b"\n"), 1)
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))

    def test_a_non_ascii_value_is_escaped_in_the_emitted_bytes_and_in_the_digest(self) -> None:
        """`ensure_ascii=True` is the half of the canonical form a JSON round-trip cannot detect."""
        objective = "clôture la tranche 6 — π \U0001f331"
        body = contract_body(objective=objective)
        done = self.run_tool("define", "--contract", str(self.store("utf8", body)))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        # The bytes are pure ASCII with the escapes spelled out, and the value survives parsing.
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))
        self.assertIn(b"cl\\u00f4ture", done.stdout)  # o-circumflex, escaped
        self.assertIn(b"\\u03c0", done.stdout)  # pi
        self.assertIn(b"\\ud83c\\udf31", done.stdout)  # the astral seedling, as a surrogate pair
        self.assertNotIn(objective.encode("utf-8"), done.stdout, "no raw UTF-8 may reach the bytes")  # the astral seedling, as a surrogate pair
        document = json.loads(done.stdout)
        self.assertEqual(document["contract"]["objective"], objective)
        # POSITIVE CONTROL for the digest: it is over the ESCAPED bytes, and it still re-derives.
        self.assertEqual(document["digest"], expected_digest(document["contract"]))
        self.assertNotEqual(document["digest"], self.define(contract_body(), name="ascii")["digest"])
        # And the sealed document round-trips through verify unchanged.
        self.assertEqual(self.verify(document["contract"], name="utf8-sealed")["verdict"], VERIFIED)

    def test_every_verdict_carries_the_same_key_set(self) -> None:
        defined = self.define(contract_body(), name="a")
        verified = self.verify(defined["contract"], name="b")
        refused = self.define(contract_body(constraints=[]), name="c")
        self.assertEqual(defined["verdict"], DEFINED)
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(refused["verdict"], REFUSED)
        for other in (verified, refused):
            self.assertEqual(sorted(defined), sorted(other))
            self.assertEqual(
                [item["slug"] for item in defined["checks"]], [item["slug"] for item in other["checks"]]
            )

    def test_the_reasons_list_is_exactly_the_checks_reasons(self) -> None:
        document = self.define(contract_body(constraints=[], stop_conditions=[]), name="two")
        flat = [reason for item in document["checks"] for reason in item["reasons"]]
        self.assertEqual(document["reasons"], flat)
        self.assertGreater(len(document["reasons"]), 1, "two broken fields must both be named")


class MalformedInputTests(ContractCase):
    """Exit 2 is reserved for a file that cannot be read as one JSON object: the question, not the
    answer, was unusable. Everything about the contract's CONTENT is a named refusal at exit 0."""

    def assert_input_error(self, *argv: str) -> bytes:
        done = self.run_tool(*argv)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"", "an input error must emit no result document")
        return done.stderr

    def test_an_absent_contract_file_is_malformed_input(self) -> None:
        # POSITIVE CONTROL: a present file at the same kind of path is exit 0.
        self.assertEqual(self.define(contract_body())["verdict"], DEFINED)
        err = self.assert_input_error("define", "--contract", str(self.work / "no-such-file.json"))
        self.assertIn(b"cannot read the mission contract", err)

    def test_a_directory_supplied_as_a_contract_is_malformed_input(self) -> None:
        (self.work / "adir").mkdir()
        err = self.assert_input_error("define", "--contract", str(self.work / "adir"))
        self.assertIn(b"not a regular file", err)

    def test_a_file_that_is_not_json_is_malformed_input(self) -> None:
        path = self.store_bytes("broken", b"{not json")
        self.assertIn(b"is not JSON", self.assert_input_error("define", "--contract", str(path)))

    def test_a_file_that_is_not_a_json_object_is_malformed_input(self) -> None:
        path = self.store_bytes("list", b"[]\n")
        self.assertIn(b"not a JSON object", self.assert_input_error("define", "--contract", str(path)))

    def test_a_duplicate_json_key_is_refused_rather_than_silently_resolved(self) -> None:
        body = contract_body()
        raw = json.dumps(body).replace('"revision": 1', '"revision": 1, "revision": 2', 1)
        if '"revision": 1' not in json.dumps(body):  # separators differ by dumps flavour
            raw = json.dumps(body).replace('"revision":1', '"revision":1,"revision":2', 1)
        path = self.store_bytes("dupe", raw.encode("utf-8"))
        self.assertIn(b"repeats the JSON key", self.assert_input_error("define", "--contract", str(path)))

    def test_a_non_finite_json_constant_is_malformed_input(self) -> None:
        path = self.store_bytes("nan", b'{"revision": NaN}\n')
        self.assertIn(b"non-finite", self.assert_input_error("define", "--contract", str(path)))

    def overflowed(self, name: str, sealed: dict[str, Any], where: str) -> Path:
        """One sealed document with `1e400` substituted at the top level or four levels in.

        `1e400` is ORDINARY JSON number syntax -- it is not one of the three literal tokens
        `parse_constant` sees -- so it parses to `inf` and only the parse hook over numbers can stop
        it. The nested case is the one a per-document top-level scan would miss.
        """
        raw = json.dumps(sealed, indent=2)
        needle, replacement = (
            ('"revision": 1', '"revision": 1e400')
            if where == "top"
            else (json.dumps(sealed["scope"]["in_scope"][0]), "1e400")
        )
        self.assertIn(needle, raw, "the substitution target moved; this fixture proves nothing")
        broken = raw.replace(needle, replacement, 1)
        self.assertIn("1e400", broken)
        return self.store_bytes(name, broken.encode("utf-8"))

    def test_a_json_number_that_overflows_to_a_non_finite_float_is_malformed_input(self) -> None:
        """agentic-sdlc-2a4b: `1e400` reached the canonical form and raised an uncaught ValueError.

        `allow_nan=False` refuses to encode `inf`, and nothing caught that, so `verify` exited 1 with
        a traceback -- while the module docstring reserves exit 2 for exactly a non-finite value. The
        two shapes below are the same defect at two depths.
        """
        sealed = self.sealed_control()
        # POSITIVE CONTROL: the untouched sealed document verifies, so each refusal below is about
        # the substituted number and not about the fixture or the verb.
        self.assertEqual(self.verify(sealed, name="control")["verdict"], VERIFIED)
        for where in ("top", "nested"):
            with self.subTest(depth=where):
                path = self.overflowed(f"overflow-{where}", sealed, where)
                err = self.assert_input_error("verify", "--contract", str(path))
                self.assertIn(b"non-finite", err)
                self.assertIn(b"1e400", err)

    def test_a_non_finite_number_in_a_supersedes_predecessor_is_malformed_input(self) -> None:
        """The same defect reached through `define`, which re-derives the predecessor's digest."""
        prior = self.sealed_control()
        follower = contract_body(revision=2, supersedes=prior["digest"], stated_at=T1)
        contract = str(self.store("rev2", follower))
        # POSITIVE CONTROL: with the untouched predecessor this exact revision seals at exit 0.
        clean = self.run_tool("define", "--contract", contract, "--supersedes", str(self.store("prior", prior)))
        self.assertEqual(clean.returncode, EXIT_OK, clean.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(clean.stdout)["verdict"], DEFINED)
        for where in ("top", "nested"):
            with self.subTest(depth=where):
                broken = self.overflowed(f"prior-overflow-{where}", prior, where)
                err = self.assert_input_error("define", "--contract", contract, "--supersedes", str(broken))
                self.assertIn(b"non-finite", err)

    def test_non_utf8_bytes_are_malformed_input(self) -> None:
        path = self.store_bytes("latin", b'{"objective": "caf\xe9"}\n')
        self.assertIn(b"is not JSON", self.assert_input_error("define", "--contract", str(path)))

    def test_an_unreadable_predecessor_is_malformed_input(self) -> None:
        err = self.assert_input_error(
            "define", "--contract", str(self.store("body", contract_body())),
            "--supersedes", str(self.work / "absent.json"),
        )
        self.assertIn(b"cannot read the prior mission contract", err)

    def test_an_expect_digest_that_is_not_a_sha256_is_malformed_input(self) -> None:
        sealed = self.sealed_control()
        err = self.assert_input_error(
            "verify", "--contract", str(self.store("sealed", sealed)), "--expect-digest", "nope"
        )
        self.assertIn(b"--expect-digest", err)

    def test_a_grammar_error_is_exit_two_and_writes_no_result_document(self) -> None:
        self.assert_input_error("define", "--not-a-flag")
        self.assert_input_error()
        self.assert_input_error("define")  # --contract is required


class ExitSpaceTests(ContractCase):
    """The module's exit space is 0, 2, and 1, and it says WHY 3 and 4 are unreachable."""

    def test_the_module_declares_why_three_and_four_are_absent(self) -> None:
        collapsed = " ".join(TOOL.read_text(encoding="utf-8").split())
        self.assertIn("a tool that can cause no effect can neither refuse before one nor admit one", collapsed)
        done = self.run_tool("define", "--help")
        self.assertEqual(done.returncode, EXIT_OK)
        help_text = " ".join(done.stdout.decode("utf-8").split())
        self.assertIn("3 and 4 do not apply", help_text)

    def test_a_refusal_is_a_derived_result_and_therefore_exit_zero(self) -> None:
        done = self.run_tool("define", "--contract", str(self.store("bad", contract_body(constraints=[]))))
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(json.loads(done.stdout)["verdict"], REFUSED)
        self.assertEqual(json.loads(done.stdout)["exit_code"], EXIT_OK)

    def test_the_tool_runs_no_subprocess_and_opens_nothing_for_writing(self) -> None:
        """The reason 3 and 4 are unreachable, checked rather than asserted in prose.

        Read with `ast` and not `in`: the module docstring says "subprocess-free", so a substring
        search over the source would find the word it is promising the absence of. What is checked is
        the import graph and the call names.
        """
        modules, calls = imports_and_calls(TOOL)
        self.assertEqual(
            modules,
            # `math` is here for `isfinite`, which is how a number that overflows to an infinity is
            # refused at the parse hook. It is pure computation: it opens nothing, spawns nothing,
            # and reads no environment, so the allowlist still admits no module that can cause an
            # effect -- which is the property this assertion exists to keep.
            {"__future__", "argparse", "collections", "hashlib", "json", "math", "pathlib", "re", "stat", "sys",
             "typing"},
            "an effect-free tool imports only the standard parsing and display surface",
        )
        forbidden = {"open", "write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename",
                     "symlink_to", "hardlink_to", "chmod", "system", "popen", "fdopen", "fsync"}
        self.assertEqual(calls & forbidden, set(), "an effect-free tool calls nothing that can write")
        # POSITIVE CONTROL: the same walk over a tool that DOES write finds both classes, so these
        # assertions are about the source rather than about names that appear nowhere in this repo.
        other_modules, other_calls = imports_and_calls(JOURNAL_TOOL)
        self.assertIn("os", other_modules)
        self.assertTrue(other_calls & forbidden, "the control tool must exercise the forbidden set")


class HostileDescriptorTests(ContractCase):
    """A display channel may cost its line; the result document may not be silently lost."""

    def test_a_closed_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        argv = ["define", "--contract", str(self.work / "no-such-file.json")]
        # POSITIVE CONTROL: with an ordinary stderr the same run exits 2 and says so.
        control = self.run_tool(*argv)
        self.assertEqual(control.returncode, EXIT_INPUT)
        self.assertIn(b"cannot read the mission contract", control.stderr)
        code, out = run_with_hostile_stderr(
            [sys.executable, "-B", str(TOOL), *argv], mode="closed", cwd=self.work
        )
        self.assertEqual(code, EXIT_INPUT, "a missing stderr must not become exit 1")
        self.assertEqual(out, b"", "an input error must emit no result document, even with no stderr")

    def test_an_epipe_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        argv = ["define", "--contract", str(self.work / "no-such-file.json")]
        code, out = run_with_hostile_stderr(
            [sys.executable, "-B", str(TOOL), *argv], mode="epipe", cwd=self.work
        )
        self.assertEqual(code, EXIT_INPUT, "a broken stderr must not become exit 120")
        self.assertEqual(out, b"")

    def test_a_grammar_error_with_no_stderr_puts_no_usage_on_stdout(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, out = run_with_hostile_stderr(
                    [sys.executable, "-B", str(TOOL), "define", "--not-a-flag"], mode=mode, cwd=self.work
                )
                self.assertEqual(code, EXIT_INPUT)
                self.assertEqual(out, b"", "argparse must not fall back to stdout, where the document lives")

    def test_a_closed_stdout_reports_an_undelivered_document(self) -> None:
        argv = ["define", "--contract", str(self.store("body", contract_body()))]
        # POSITIVE CONTROL: with an ordinary stdout the same run delivers a sealed contract.
        control = self.run_tool(*argv)
        self.assertEqual(control.returncode, EXIT_OK)
        self.assertEqual(json.loads(control.stdout)["verdict"], DEFINED)
        code, err = run_with_hostile_stdout(
            [sys.executable, "-B", str(TOOL), *argv], mode="closed", cwd=self.work
        )
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn(b"handed no stdout", err)

    def test_an_epipe_stdout_reports_an_undelivered_document(self) -> None:
        argv = ["define", "--contract", str(self.store("body", contract_body()))]
        code, err = run_with_hostile_stdout(
            [sys.executable, "-B", str(TOOL), *argv], mode="epipe", cwd=self.work
        )
        self.assertEqual(code, EXIT_INTERNAL, "a broken stdout must not become exit 120")
        self.assertIn(b"not delivered", err)

    def test_help_with_no_stdout_exits_cleanly_instead_of_crashing(self) -> None:
        # POSITIVE CONTROL: with an ordinary stdout, help is printed and exits 0.
        control = self.run_tool("define", "--help")
        self.assertEqual(control.returncode, EXIT_OK)
        self.assertIn(b"--contract", control.stdout)
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, _ = run_with_hostile_stdout(
                    [sys.executable, "-B", str(TOOL), "define", "--help"], mode=mode, cwd=self.work
                )
                self.assertEqual(code, EXIT_OK)

    def test_both_streams_hostile_at_once_still_classifies(self) -> None:
        argv = ["define", "--contract", str(self.store("body", contract_body()))]
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&- 2>&-; exec "$@"', "sh", sys.executable, "-B", str(TOOL), *argv],
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_INTERNAL)

    def test_both_streams_epipe_at_once_still_classifies(self) -> None:
        argv = [sys.executable, "-B", str(TOOL), "define", "--contract", str(self.store("body", contract_body()))]
        out_read, out_write = os.pipe()
        err_read, err_write = os.pipe()
        os.close(out_read)
        os.close(err_read)
        try:
            child = subprocess.Popen(argv, stdout=out_write, stderr=err_write, cwd=str(self.work),
                                     env=constructed_environment())
        finally:
            os.close(out_write)
            os.close(err_write)
        self.assertEqual(child.wait(), EXIT_INTERNAL, "two broken streams must not become exit 120")


class EnvironmentTests(ContractCase):
    """The tool reads no environment variable, and its verdict does not move when one is set."""

    def test_the_tool_reads_no_environment_variable(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)
        # POSITIVE CONTROL: the same grep over a tool that DOES read one finds it.
        self.assertIn("os.environ", JOURNAL_TOOL.read_text(encoding="utf-8"))

    def test_a_verdict_does_not_change_when_an_unrelated_variable_is_set(self) -> None:
        argv = [sys.executable, "-B", str(TOOL), "define", "--contract", str(self.store("body", contract_body()))]
        first = subprocess.run(argv, capture_output=True, cwd=str(self.work), check=False,
                               env=constructed_environment())
        second = subprocess.run(
            argv,
            capture_output=True,
            cwd=str(self.work),
            check=False,
            env=constructed_environment(
                {"AGENTIC_SDLC_MISSION_CONTRACT": "defined", "TZ": "Pacific/Kiritimati", "SOURCE_DATE_EPOCH": "0"}
            ),
        )
        self.assertEqual(first.returncode, EXIT_OK)
        self.assertEqual(second.stdout, first.stdout)


if __name__ == "__main__":
    unittest.main()
