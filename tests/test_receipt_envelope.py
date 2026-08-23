"""Tests for the receipt envelope and its typed correlation-graph checker.

Six kinds of test live here and they check different things.

The ENVELOPE tests hand one document to `verify`. Every NEGATIVE case carries a POSITIVE CONTROL in
the same test -- the unmutated receipt is asserted to reach `verified` FIRST -- so a test that
stopped exercising its guard would also have to stop reaching that verdict.

The SHAPE-VERSUS-GRAPH tests are the load-bearing ones. `check-graph` runs the same envelope check
over every line before it derives one finding, so any relational property `verify` refused would make
a finding UNREACHABLE. Two tests assert the split directly: a repeated reference and a self-naming
reference both `verify`, and both are reported as findings by `check-graph`.

The GRAPH tests build small sets and assert the exact findings. Each finding's absence is proved
meaningful by a control in the same test that makes it appear (or disappear), because "no finding"
is the assertion most likely to pass for the wrong reason.

The ITERATIVE-WALK tests run a five-thousand-receipt chain, which is five times the interpreter's
default recursion limit, and assert both that the acyclic chain is clean and that a loop closed at
its far end is found. A recursive walk cannot pass either.

The CANONICAL-FORM tests assert BYTES, not parsed values, and one of them carries a non-ASCII body,
because `ensure_ascii=True` is the half of the canonical form a JSON round-trip cannot detect.

The HOSTILE-DESCRIPTOR cases run the tool with a stderr or a stdout it cannot write to -- `2>&-` and
a real pipe whose reader is already gone -- because a display channel must cost the display line and
never the classified exit code, while the one result document is the evidence: a graph checked and
not reported is not a success.
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
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "receipt-envelope.py"
#: Used only as the POSITIVE CONTROL for the two source-level greps at the bottom of this module:
#: a sibling that DOES read the environment and DOES write, so an empty answer from either
#: assertion is evidence rather than a grep over a name nothing in this repo carries.
CONTROL_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "pass-budget.py"

ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"
RESULT_SCHEMA = "agentic-sdlc/receipt-envelope-result@1"

VERIFIED = "verified"
GRAPH_CLEAN = "graph-clean"
GRAPH_DEFECTIVE = "graph-defective"
REFUSED = "refused"

EXIT_OK = 0
#: The undelivered-document code. A result this tool derived but could not put on stdout is neither a
#: success nor an input error, and 120 is not in the module's exit space at all.
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The six receipt families, exactly as the tool declares them.
KINDS = (
    "distribution-activation",
    "incident-recovery",
    "integration-completion",
    "probe-qualification",
    "route-credential-lifecycle",
    "workflow-wave-node-attempt",
)
NODE = "workflow-wave-node-attempt"
WAVE = "integration-completion"

#: The six typed relations a child may hold to a direct ancestor.
RELATIONS = (
    "contained-by",
    "derived-from",
    "references-evidence",
    "remediates",
    "retries",
    "supersedes",
)

#: The closed finding vocabulary. `test_the_reported_finding_vocabulary_is_exactly_this_closed_set`
#: proves every one of them is reachable, so this tuple cannot rot into a superset.
FINDINGS = ("cyclic", "dangling", "duplicate", "duplicate-id", "kind-incompatible")

#: The closed key set of one finding record: a consumer reads one shape for all five findings.
FINDING_KEYS = (
    "ancestor_receipt_id",
    "detail",
    "finding",
    "implicated_receipt_ids",
    "receipt_id",
    "relation",
)

#: Every refusal must name one of these. The reference keys are included because a nested mistake
#: must be named at the level the caller wrote it, not as "the ancestors are wrong".
FIELD_NAMES = (
    "schema",
    "receipt_kind",
    "receipt_id",
    "stated_at",
    "emitting_plane",
    "content_digest",
    "ancestors",
    "body",
    "expected_kind",
    "relation",
)

T0 = "2026-08-19T02:00:00Z"

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


def expected_digest(body: dict[str, Any]) -> str:
    """The digest contract, re-expressed here so a drifted tool fails rather than agrees with itself.

    sha256 over `canonical(body)`. Re-expressed rather than imported: the tool has a hyphen in its
    name, so a plain `import` statement cannot name it, and a shared implementation would make this
    assertion vacuous.
    """
    return hashlib.sha256(canonical(body)).hexdigest()


def reference(receipt_id: str, *, kind: str = NODE, relation: str = "contained-by") -> dict[str, str]:
    """One typed ancestor reference: who, what kind it is believed to be, and how."""
    return {"expected_kind": kind, "receipt_id": receipt_id, "relation": relation}


def receipt(**overrides: Any) -> dict[str, Any]:
    """One complete, valid receipt: the positive control every negative case starts from.

    The content digest is DERIVED from whatever body survives the overrides, unless a test overrode
    the digest itself. A test that supplies a malformed body still gets a well-shaped digest field, so
    the refusal it provokes names the body rather than the digest.
    """
    document: dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "receipt_kind": NODE,
        "receipt_id": "node-a",
        "stated_at": T0,
        "emitting_plane": "claude",
        "content_digest": "",
        "ancestors": [],
        "body": {"schema": "agentic-sdlc/wave-node-attempt-payload@1", "disposition": "admitted-success"},
    }
    document.update(overrides)
    if "content_digest" not in overrides:
        body = document.get("body")
        document["content_digest"] = expected_digest(body) if isinstance(body, dict) and body else "0" * 64
    return document


def chain(length: int, *, close_the_loop: bool = False) -> list[dict[str, Any]]:
    """A chain of `length` receipts, each naming the NEXT id as its one ancestor.

    Both the zero padding and the direction are load-bearing. The walk starts from the smallest id, so
    this chain's deepest descent begins at its first start and the whole depth is forced. A chain
    pointing the other way -- each receipt naming its numeric predecessor -- lets a RECURSIVE walk
    pass a depth test anyway, because each later start descends exactly one frame before meeting a
    node the previous start already finished. That was measured, not assumed: with the chain reversed,
    a recursive implementation of this tool's own walk passed a five-thousand-receipt acyclic case.
    """
    ids = [f"node-{index:05d}" for index in range(length)]
    documents: list[dict[str, Any]] = []
    for position, receipt_id in enumerate(ids):
        if position + 1 < length:
            ancestors = [reference(ids[position + 1])]
        else:
            ancestors = [reference(ids[0])] if close_the_loop else []
        documents.append(receipt(receipt_id=receipt_id, ancestors=ancestors))
    return documents


def imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    """The module's top-level import names and every called name, read with `ast`.

    A substring search would be fooled by prose: this tool's own docstring contains the word
    "subprocess-free", and an `assertNotIn("subprocess", source)` would fail on the promise itself.
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


def compiled_patterns(source: str) -> list[str]:
    """Every literal pattern handed to a `.compile(...)` call, read with `ast`.

    The point is to check the PATTERNS rather than the prose around them: a module that explains why
    it avoids a character class contains the class's spelling in its own docstring.
    """
    patterns: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "compile" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            patterns.append(first.value)
    return patterns


def run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Two shapes, kept separate because they produce DIFFERENT wrong exit codes and neither is exotic:

        closed  `2>&-`. CPython then starts with `sys.stderr is None`, so the FIRST
                `sys.stderr.write` raises `AttributeError` and the classified code becomes 1.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write raises
                EPIPE and leaves bytes pending that CPython flushes again while finalizing, which
                replaces the exit code with 120.

    Stderr is deliberately NOT captured: capturing it would hand the child a writable stream and test
    nothing.
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


class EnvelopeCase(unittest.TestCase):
    """Verifies receipts and checks receipt sets, each in its own constructed scratch directory."""

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

    def store_set(self, name: str, documents: list[dict[str, Any]]) -> Path:
        path = self.work / f"{name}.jsonl"
        path.write_text(
            "".join(json.dumps(document, ensure_ascii=False) + "\n" for document in documents),
            encoding="utf-8",
        )
        return path

    def store_bytes(self, name: str, raw: bytes) -> Path:
        path = self.work / name
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

    def verify(self, document: dict[str, Any], *, name: str = "receipt") -> dict[str, Any]:
        done = self.run_tool("verify", "--receipt", str(self.store(name, document)))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return json.loads(done.stdout)

    def check_graph(self, documents: list[dict[str, Any]], *, name: str = "set") -> dict[str, Any]:
        done = self.run_tool("check-graph", "--receipts", str(self.store_set(name, documents)))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return json.loads(done.stdout)

    def assert_verified(self, document: dict[str, Any], *, name: str = "control") -> dict[str, Any]:
        result = self.verify(document, name=name)
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])
        return result

    def assert_refused(self, result: dict[str, Any], needle: str) -> None:
        self.assertEqual(result["verdict"], REFUSED, result["reasons"])
        for key in ("receipt_id", "receipt_kind", "content_digest"):
            self.assertIsNone(result[key], f"a refused receipt publishes no {key}")
        self.assertEqual(result["findings"], [], "a set with an unadmitted member is not a graph")
        joined = " | ".join(result["reasons"])
        self.assertIn(needle, joined)
        for reason in result["reasons"]:
            # Every refusal NAMES a field and says what was wrong with it, so a bare "invalid
            # receipt" is unreachable. The check is the positive property rather than a banned word:
            # one of the envelope's own field names must appear in the sentence.
            self.assertTrue(
                any(field in reason for field in FIELD_NAMES),
                f"a refusal that names no field is useless to the human it asks: {reason}",
            )
            self.assertGreater(len(reason), 30, reason)

    def findings_named(self, result: dict[str, Any], name: str) -> list[dict[str, Any]]:
        return [item for item in result["findings"] if item["finding"] == name]

    def assert_clean(self, result: dict[str, Any], expected_receipts: int) -> None:
        self.assertEqual(result["verdict"], GRAPH_CLEAN, result["findings"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["receipts_checked"], expected_receipts)
        self.assertIs(result["resolution_checked"], True)


class EnvelopeTests(EnvelopeCase):
    """The closed envelope: exactly eight keys, each well-formed, and the digest re-derives."""

    def test_a_well_formed_receipt_verifies_and_its_digest_re_derives(self) -> None:
        document = receipt(ancestors=[reference("wave-1", kind=WAVE)])
        result = self.verify(document)
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        self.assertEqual(result["command"], "verify")
        self.assertEqual(result["verdict"], VERIFIED)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["receipt_id"], "node-a")
        self.assertEqual(result["receipt_kind"], NODE)
        self.assertEqual(result["content_digest"], expected_digest(document["body"]))
        self.assertEqual(result["content_digest"], document["content_digest"])
        # A verify result never republishes the receipt: it names and digests it instead.
        self.assertIsNone(result["receipts_checked"])
        self.assertIsNone(result["resolution_checked"])
        self.assertEqual(result["findings"], [])

    def test_every_receipt_kind_verifies(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assert_verified(receipt(receipt_kind=kind), name=f"kind-{kind}")

    def test_every_relation_verifies(self) -> None:
        for relation in RELATIONS:
            with self.subTest(relation=relation):
                document = receipt(ancestors=[reference("wave-1", kind=WAVE, relation=relation)])
                self.assert_verified(document, name=f"relation-{relation}")

    def test_a_receipt_with_no_ancestor_verifies(self) -> None:
        """The first receipt of a lifecycle has no ancestor, and the empty list is its statement."""
        result = self.assert_verified(receipt(ancestors=[]), name="root")
        self.assertEqual(result["receipt_id"], "node-a")

    def test_every_required_envelope_field_missing_refuses_by_its_own_name(self) -> None:
        keys = sorted(receipt())
        self.assertEqual(len(keys), 8, "the closed envelope key set changed; update this test deliberately")
        for key in keys:
            with self.subTest(missing=key):
                # POSITIVE CONTROL: the same receipt WITH the field verifies.
                self.assert_verified(receipt(), name=f"control-{key}")
                document = receipt()
                del document[key]
                self.assert_refused(self.verify(document, name=f"missing-{key}"), f"carries no {key}")

    def test_an_unknown_envelope_field_refuses_rather_than_being_ignored(self) -> None:
        self.assert_verified(receipt(), name="control")
        # `effect_state` is one of issue 20's envelope fields this version deliberately does not own,
        # so it is exactly the field a writer would add by hand: refused, not silently carried.
        result = self.verify(receipt(effect_state="none"), name="extra")
        self.assert_refused(result, "effect_state")
        self.assertIn("belong inside body", " | ".join(result["reasons"]))

    def test_a_wrong_schema_tag_refuses(self) -> None:
        self.assert_refused(self.verify(receipt(schema="agentic-sdlc/receipt-envelope@2"), name="v2"), "schema")

    def test_an_out_of_vocabulary_receipt_kind_refuses(self) -> None:
        self.assert_verified(receipt(), name="control")
        self.assert_refused(self.verify(receipt(receipt_kind="whatever-happened"), name="kind"), "whatever-happened")

    def test_an_out_of_vocabulary_relation_refuses(self) -> None:
        document = receipt(ancestors=[reference("wave-1", kind=WAVE, relation="vaguely-related-to")])
        self.assert_refused(self.verify(document, name="relation"), "vaguely-related-to")

    def test_an_out_of_vocabulary_expected_kind_refuses(self) -> None:
        document = receipt(ancestors=[reference("wave-1", kind="some-other-family")])
        self.assert_refused(self.verify(document, name="expected"), "some-other-family")

    def test_a_reference_missing_a_key_refuses(self) -> None:
        for key in sorted(reference("wave-1")):
            with self.subTest(missing=key):
                self.assert_verified(receipt(ancestors=[reference("wave-1", kind=WAVE)]), name=f"c-{key}")
                item = reference("wave-1", kind=WAVE)
                del item[key]
                result = self.verify(receipt(ancestors=[item]), name=f"ref-{key}")
                self.assert_refused(result, f"ancestors[0] carries no {key}")

    def test_a_reference_with_an_unknown_key_refuses(self) -> None:
        item = dict(reference("wave-1", kind=WAVE), confidence=0.9)
        self.assert_refused(self.verify(receipt(ancestors=[item]), name="refextra"), "confidence")

    def test_a_reference_that_is_not_an_object_refuses(self) -> None:
        # A list is the interesting wrong type: `set(a_list)` succeeds, so without the type guard the
        # reference's keys would be looked for among the list's OWN entries and refused as "carries no
        # relation", which names the wrong mistake.
        self.assert_refused(self.verify(receipt(ancestors=[["wave-1"]]), name="reflist"), "is not a JSON object")

    def test_an_ancestors_value_that_is_not_a_list_refuses(self) -> None:
        for bad in (None, {}, "wave-1", 3):
            with self.subTest(ancestors=bad):
                self.assert_refused(self.verify(receipt(ancestors=bad), name="anc"), "ancestors is not a JSON list")

    def test_a_body_that_is_not_a_non_empty_object_refuses(self) -> None:
        for bad in (None, {}, [], "sealed elsewhere", 7):
            with self.subTest(body=bad):
                self.assert_refused(self.verify(receipt(body=bad), name="body"), "body is not a non-empty JSON object")

    def test_a_receipt_id_that_is_not_a_lowercase_ascii_token_refuses(self) -> None:
        self.assert_verified(receipt(receipt_id="node-a-1"), name="control")
        for bad in ("Node-A", "node a", "-node", "node-", "node_a", "node.a", "", None, 7, ["node-a"]):
            with self.subTest(receipt_id=bad):
                result = self.verify(receipt(receipt_id=bad), name="id")
                self.assert_refused(result, "receipt_id is not a lowercase ASCII token")

    def test_a_receipt_id_spelled_in_arabic_indic_digits_refuses(self) -> None:
        """`\\d` and `\\w` match Unicode digits, not only ASCII 0-9, so an admitted Arabic-Indic id
        would be a DIFFERENT string that reads like an existing one -- and every reference naming the
        ASCII spelling would be reported dangling with no field named."""
        # POSITIVE CONTROL: the same id spelled in ASCII digits is admitted.
        self.assert_verified(receipt(receipt_id="node-2026"), name="ascii")
        self.assert_refused(self.verify(receipt(receipt_id="node-٢٠٢٦"), name="arabic-indic"), "receipt_id")

    def test_an_emitting_plane_that_is_not_a_token_refuses(self) -> None:
        # The plane vocabulary is deliberately OPEN, so the control is a plane name this repository
        # does not know: what is enforced is one spelling, not one closed list.
        self.assert_verified(receipt(emitting_plane="some-future-plane"), name="control")
        for bad in ("Claude", "claude plane", "", None):
            with self.subTest(emitting_plane=bad):
                self.assert_refused(self.verify(receipt(emitting_plane=bad), name="plane"), "emitting_plane")

    def test_a_stated_at_that_is_not_a_fixed_width_instant_refuses(self) -> None:
        for bad in ("2026-08-19", "2026-08-19T02:00:00.000Z", "2026-08-19 02:00:00Z", 1755561600, None):
            with self.subTest(stated_at=bad):
                self.assert_refused(self.verify(receipt(stated_at=bad), name="when"), "stated_at")

    def test_a_stated_at_spelled_in_arabic_indic_digits_refuses(self) -> None:
        self.assert_verified(receipt(stated_at="2020-08-19T02:00:00Z"), name="ascii")
        result = self.verify(receipt(stated_at="٢٠٢٠-٠٨-١٩T٠٢:٠٠:٠٠Z"), name="arabic-indic")
        self.assert_refused(result, "stated_at")

    def test_a_content_digest_that_is_not_64_lowercase_hex_refuses(self) -> None:
        for bad in ("F" * 64, "abc", "g" * 64, 12345, None):
            with self.subTest(content_digest=bad):
                # The precise needle: a digest that is not a sha256 at all is refused for its SHAPE,
                # not merely swept up by the re-derivation mismatch that would also fire on any
                # 64-character hex string. Those are two guards and the caller is told which.
                result = self.verify(receipt(content_digest=bad), name="shape")
                self.assert_refused(result, "64 lowercase hexadecimal")

    def test_an_edited_body_refuses_because_the_digest_no_longer_re_derives(self) -> None:
        document = receipt()
        self.assert_verified(document, name="control")
        edited = receipt(
            body={"schema": "agentic-sdlc/wave-node-attempt-payload@1", "disposition": "approved-skip"},
            content_digest=document["content_digest"],
        )
        self.assert_refused(self.verify(edited, name="edited"), "does not re-derive")

    def test_the_digest_seals_the_body_and_not_the_envelope(self) -> None:
        """A STATED RESIDUAL, asserted rather than trusted: `content_digest` covers the body only, so
        an edited envelope field still re-derives. The positive control is that an edited BODY does
        not, which is what keeps this a documented limit rather than a broken digest."""
        document = receipt()
        result = self.verify(dict(document, stated_at="1999-01-01T00:00:00Z"), name="restamped")
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])
        self.assertEqual(result["content_digest"], document["content_digest"])
        residuals = " | ".join(result["residuals"])
        self.assertIn("the content digest seals the body only", residuals)
        # POSITIVE CONTROL: the same digest over a changed body does NOT re-derive.
        edited = dict(document)
        edited["body"] = dict(document["body"], disposition="explicit-block")
        self.assert_refused(self.verify(edited, name="edited-body"), "does not re-derive")

    def test_input_whitespace_and_key_order_do_not_reach_the_digest(self) -> None:
        document = receipt()
        pretty = self.verify(document, name="pretty")["content_digest"]
        reordered = {key: document[key] for key in reversed(list(document))}
        self.assertNotEqual(list(reordered), list(document))  # POSITIVE CONTROL: the input differs
        packed = self.work / "packed.json"
        packed.write_bytes(json.dumps(reordered, separators=(",", ":")).encode("utf-8"))
        done = self.run_tool("verify", "--receipt", str(packed))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(done.stdout)["content_digest"], pretty)

    def test_a_changed_body_changes_the_digest(self) -> None:
        """The other half of digest stability: a digest that ignored content would pass every test
        above, including the re-derivation ones."""
        first = self.verify(receipt(), name="a")["content_digest"]
        second = self.verify(
            receipt(body={"schema": "agentic-sdlc/wave-node-attempt-payload@1", "disposition": "failure"}),
            name="b",
        )["content_digest"]
        self.assertNotEqual(first, second)


class ShapeVersusGraphTests(EnvelopeCase):
    """`verify` derives no relational fact, because doing so would make a finding UNREACHABLE.

    `check-graph` runs the same envelope check over every line before deriving one finding. If
    `verify` refused a repeated or self-naming reference, no receipt set carrying one could ever be
    admitted, and the `duplicate` and `cyclic` findings would be dead vocabulary.
    """

    def test_verify_admits_a_repeated_reference_so_the_duplicate_finding_is_reachable(self) -> None:
        document = receipt(ancestors=[reference("wave-1", kind=WAVE), reference("wave-1", kind=WAVE)])
        self.assert_verified(document, name="repeated")
        result = self.check_graph([receipt(receipt_id="wave-1", receipt_kind=WAVE), document])
        self.assertEqual(result["verdict"], GRAPH_DEFECTIVE)
        self.assertEqual([item["finding"] for item in result["findings"]], ["duplicate"])

    def test_verify_admits_a_self_naming_reference_so_the_cyclic_finding_is_reachable(self) -> None:
        document = receipt(ancestors=[reference("node-a")])
        self.assert_verified(document, name="self")
        result = self.check_graph([document])
        self.assertEqual([item["finding"] for item in result["findings"]], ["cyclic"])
        self.assertEqual(result["findings"][0]["implicated_receipt_ids"], ["node-a"])


class GraphCleanTests(EnvelopeCase):
    """A clean graph says so explicitly, and says how much it checked."""

    def wave_and_two_nodes(self) -> list[dict[str, Any]]:
        return [
            receipt(receipt_id="wave-1", receipt_kind=WAVE),
            receipt(receipt_id="node-a", ancestors=[reference("wave-1", kind=WAVE)]),
            receipt(
                receipt_id="node-b",
                ancestors=[reference("wave-1", kind=WAVE), reference("node-a", relation="retries")],
            ),
        ]

    def test_a_clean_graph_reports_itself_clean_explicitly(self) -> None:
        result = self.check_graph(self.wave_and_two_nodes())
        self.assert_clean(result, 3)
        self.assertEqual(result["command"], "check-graph")
        self.assertEqual(result["reasons"], [])
        self.assertIn("no duplicate, dangling, cyclic, or kind-incompatible reference", result["consequence"])
        # A graph result never republishes one receipt's identity: the set is the subject.
        for key in ("receipt_id", "receipt_kind", "content_digest"):
            self.assertIsNone(result[key], key)

    def test_two_receipts_naming_one_ancestor_are_a_fan_in_and_not_a_duplicate(self) -> None:
        """`duplicate` is one receipt naming one ancestor twice with one relation. Fan-in -- the
        ordinary shape of a wave -- must stay clean, or the finding would fire on every real set."""
        result = self.check_graph(self.wave_and_two_nodes())
        self.assert_clean(result, 3)
        # POSITIVE CONTROL: moving both references onto ONE receipt does report duplicate.
        documents = self.wave_and_two_nodes()
        documents[1] = receipt(
            receipt_id="node-a", ancestors=[reference("wave-1", kind=WAVE), reference("wave-1", kind=WAVE)]
        )
        control = self.check_graph(documents, name="control")
        self.assertEqual([item["finding"] for item in control["findings"]], ["duplicate"])

    def test_the_same_ancestor_under_two_different_relations_is_clean(self) -> None:
        documents = [
            receipt(receipt_id="node-a"),
            receipt(
                receipt_id="node-b",
                ancestors=[reference("node-a", relation="retries"), reference("node-a", relation="derived-from")],
            ),
        ]
        self.assert_clean(self.check_graph(documents), 2)
        # POSITIVE CONTROL: the same two references under ONE relation are a duplicate.
        documents[1] = receipt(
            receipt_id="node-b",
            ancestors=[reference("node-a", relation="retries"), reference("node-a", relation="retries")],
        )
        control = self.check_graph(documents, name="control")
        self.assertEqual([item["finding"] for item in control["findings"]], ["duplicate"])

    def test_every_relation_resolves_in_a_graph(self) -> None:
        documents = [receipt(receipt_id="node-a")]
        documents.extend(
            receipt(receipt_id=f"node-{index}", ancestors=[reference("node-a", relation=relation)])
            for index, relation in enumerate(RELATIONS, start=1)
        )
        self.assert_clean(self.check_graph(documents), len(RELATIONS) + 1)


class GraphFindingTests(EnvelopeCase):
    """Each of the five findings, with a control in the same test that makes it appear or vanish."""

    def test_a_reference_with_no_target_in_the_set_is_dangling(self) -> None:
        documents = [receipt(receipt_id="node-a", ancestors=[reference("wave-1", kind=WAVE)])]
        result = self.check_graph(documents)
        self.assertEqual(result["verdict"], GRAPH_DEFECTIVE)
        found = self.findings_named(result, "dangling")
        self.assertEqual(len(found), 1, result["findings"])
        self.assertEqual(found[0]["receipt_id"], "node-a")
        self.assertEqual(found[0]["ancestor_receipt_id"], "wave-1")
        self.assertEqual(found[0]["relation"], "contained-by")
        self.assertEqual(found[0]["implicated_receipt_ids"], ["node-a", "wave-1"])
        # POSITIVE CONTROL: adding the named target to the same set clears the finding.
        documents.insert(0, receipt(receipt_id="wave-1", receipt_kind=WAVE))
        self.assert_clean(self.check_graph(documents, name="control"), 2)

    def test_two_references_to_one_ancestor_with_one_relation_are_duplicate(self) -> None:
        documents = [
            receipt(receipt_id="wave-1", receipt_kind=WAVE),
            receipt(
                receipt_id="node-a",
                ancestors=[reference("wave-1", kind=WAVE), reference("wave-1", kind=WAVE)],
            ),
        ]
        result = self.check_graph(documents)
        found = self.findings_named(result, "duplicate")
        self.assertEqual(len(found), 1, result["findings"])
        self.assertEqual(found[0]["receipt_id"], "node-a")
        self.assertEqual(found[0]["ancestor_receipt_id"], "wave-1")
        self.assertEqual(found[0]["relation"], "contained-by")
        self.assertEqual(found[0]["implicated_receipt_ids"], ["node-a", "wave-1"])
        self.assertIn("2 times", found[0]["detail"])
        # POSITIVE CONTROL: one reference instead of two is clean.
        documents[1] = receipt(receipt_id="node-a", ancestors=[reference("wave-1", kind=WAVE)])
        self.assert_clean(self.check_graph(documents, name="control"), 2)

    def test_a_target_whose_kind_disagrees_with_the_expected_kind_is_kind_incompatible(self) -> None:
        documents = [
            receipt(receipt_id="wave-1", receipt_kind=WAVE),
            receipt(receipt_id="node-a", ancestors=[reference("wave-1", kind="probe-qualification")]),
        ]
        result = self.check_graph(documents)
        found = self.findings_named(result, "kind-incompatible")
        self.assertEqual(len(found), 1, result["findings"])
        self.assertEqual(found[0]["implicated_receipt_ids"], ["node-a", "wave-1"])
        self.assertIn("probe-qualification", found[0]["detail"])
        self.assertIn(WAVE, found[0]["detail"])
        # POSITIVE CONTROL: expecting the kind the target actually carries is clean.
        documents[1] = receipt(receipt_id="node-a", ancestors=[reference("wave-1", kind=WAVE)])
        self.assert_clean(self.check_graph(documents, name="control"), 2)

    def test_a_two_receipt_loop_is_cyclic(self) -> None:
        documents = [
            receipt(receipt_id="node-a", ancestors=[reference("node-b")]),
            receipt(receipt_id="node-b", ancestors=[reference("node-a")]),
        ]
        result = self.check_graph(documents)
        found = self.findings_named(result, "cyclic")
        self.assertEqual(len(found), 1, result["findings"])
        self.assertEqual(found[0]["implicated_receipt_ids"], ["node-a", "node-b"])
        self.assertIn("node-a -> node-b -> node-a", found[0]["detail"])
        # POSITIVE CONTROL: breaking one edge of the same pair is clean.
        documents[1] = receipt(receipt_id="node-b")
        self.assert_clean(self.check_graph(documents, name="control"), 2)

    def test_a_three_receipt_loop_reports_one_finding_naming_all_three(self) -> None:
        documents = [
            receipt(receipt_id="node-a", ancestors=[reference("node-c")]),
            receipt(receipt_id="node-b", ancestors=[reference("node-a")]),
            receipt(receipt_id="node-c", ancestors=[reference("node-b")]),
        ]
        found = self.findings_named(self.check_graph(documents), "cyclic")
        self.assertEqual(len(found), 1)
        self.assertEqual(sorted(found[0]["implicated_receipt_ids"]), ["node-a", "node-b", "node-c"])
        # The loop is reported in traversal order, rotated so its smallest id leads, so the same loop
        # has one spelling no matter which receipt the walk reached first.
        self.assertEqual(found[0]["implicated_receipt_ids"][0], "node-a")

    def test_a_loop_entered_through_a_tail_implicates_only_the_loop_and_rotates_to_its_smallest_id(
        self,
    ) -> None:
        """The walk descends aaa -> zzz -> yyy -> zzz. The back edge closes yyy and zzz into a loop;
        aaa is a TAIL that only leads into it and is not itself on the loop. The loop-extraction slice
        must start at the point the walk RE-ENTERED the loop (zzz), not at the walk's own start (aaa),
        and the canonical rotation must then lead with the loop's smallest id (yyy) so the same loop
        has one spelling regardless of where the walk began descending."""
        documents = [
            receipt(receipt_id="aaa", ancestors=[reference("zzz")]),
            receipt(receipt_id="zzz", ancestors=[reference("yyy")]),
            receipt(receipt_id="yyy", ancestors=[reference("zzz")]),
        ]
        result = self.check_graph(documents)
        self.assertEqual(result["verdict"], GRAPH_DEFECTIVE)
        self.assertEqual([item["finding"] for item in result["findings"]], ["cyclic"])
        found = result["findings"][0]
        self.assertEqual(found["implicated_receipt_ids"], ["yyy", "zzz"], "aaa is a tail, not a loop member")
        self.assertEqual(found["receipt_id"], "yyy", "the canonical rotation leads with the loop's smallest id")
        self.assertIn("yyy -> zzz -> yyy", found["detail"])
        # POSITIVE CONTROL: the same graph without the closing edge (yyy's reference back to zzz) is clean.
        documents[2] = receipt(receipt_id="yyy", ancestors=[])
        self.assert_clean(self.check_graph(documents, name="control"), 3)

    def test_a_repeated_receipt_id_is_duplicate_id_and_stops_reference_resolution(self) -> None:
        """A repeated id makes every reference naming it ambiguous, so resolution is not derived at
        all -- and `resolution_checked` is what tells a consumer that an empty dangling list means
        "not checked" rather than "clean"."""
        documents = [
            receipt(receipt_id="node-a"),
            receipt(receipt_id="node-a", receipt_kind=WAVE),
            receipt(receipt_id="node-b", ancestors=[reference("ghost-1")]),
        ]
        result = self.check_graph(documents)
        self.assertEqual(result["verdict"], GRAPH_DEFECTIVE)
        self.assertIs(result["resolution_checked"], False)
        self.assertEqual([item["finding"] for item in result["findings"]], ["duplicate-id"])
        self.assertEqual(result["findings"][0]["implicated_receipt_ids"], ["node-a"])
        self.assertIn("lines 1, 2", result["findings"][0]["detail"])
        self.assertEqual(self.findings_named(result, "dangling"), [], "an ambiguous set derives no resolution")
        # POSITIVE CONTROL: with unique ids the SAME dangling reference is reported, so the absence
        # above is the ambiguity rule and not a checker that never reports dangling.
        documents[1] = receipt(receipt_id="node-c", receipt_kind=WAVE)
        control = self.check_graph(documents, name="control")
        self.assertIs(control["resolution_checked"], True)
        self.assertEqual([item["finding"] for item in control["findings"]], ["dangling"])

    def test_an_ambiguous_set_still_reports_a_duplicate_reference(self) -> None:
        """`duplicate` is intrinsic to one document: no reference has to resolve for it to be true,
        so it survives the ambiguity that suppresses the resolution findings."""
        documents = [
            receipt(receipt_id="node-a"),
            receipt(receipt_id="node-a"),
            receipt(receipt_id="node-b", ancestors=[reference("ghost-1"), reference("ghost-1")]),
        ]
        result = self.check_graph(documents)
        self.assertIs(result["resolution_checked"], False)
        self.assertEqual(
            [item["finding"] for item in result["findings"]], ["duplicate", "duplicate-id"]
        )

    def test_every_finding_carries_the_same_closed_key_set_and_names_its_implicated_ids(self) -> None:
        documents = [
            receipt(receipt_id="node-a", ancestors=[reference("ghost-1"), reference("node-b"), reference("node-b")]),
            receipt(receipt_id="node-b", ancestors=[reference("node-a")]),
            receipt(receipt_id="wave-1", receipt_kind=WAVE, ancestors=[reference("node-a", kind="probe-qualification")]),
        ]
        result = self.check_graph(documents)
        self.assertEqual(
            [item["finding"] for item in result["findings"]],
            ["cyclic", "dangling", "duplicate", "kind-incompatible"],
            "four findings, sorted by their own names",
        )
        for item in result["findings"]:
            self.assertEqual(sorted(item), sorted(FINDING_KEYS))
            self.assertIn(item["finding"], FINDINGS)
            self.assertGreater(len(item["implicated_receipt_ids"]), 0, item)
            for receipt_id in item["implicated_receipt_ids"]:
                self.assertIn(receipt_id, item["detail"], "a finding names its implicated ids in prose too")
            self.assertGreater(len(item["detail"]), 40, item)

    def test_the_reported_finding_vocabulary_is_exactly_this_closed_set(self) -> None:
        """Every one of the five findings is REACHABLE, so the vocabulary cannot rot into a superset
        that names a defect no input can produce."""
        sets = {
            "dangling": [receipt(receipt_id="node-a", ancestors=[reference("ghost-1")])],
            "duplicate": [
                receipt(receipt_id="node-b"),
                receipt(receipt_id="node-a", ancestors=[reference("node-b"), reference("node-b")]),
            ],
            "kind-incompatible": [
                receipt(receipt_id="wave-1", receipt_kind=WAVE),
                receipt(receipt_id="node-a", ancestors=[reference("wave-1")]),
            ],
            "cyclic": [receipt(receipt_id="node-a", ancestors=[reference("node-a")])],
            "duplicate-id": [receipt(receipt_id="node-a"), receipt(receipt_id="node-a")],
        }
        reported: set[str] = set()
        for name, documents in sets.items():
            with self.subTest(finding=name):
                result = self.check_graph(documents, name=f"set-{name}")
                self.assertEqual(result["verdict"], GRAPH_DEFECTIVE, result)
                names = {item["finding"] for item in result["findings"]}
                self.assertIn(name, names)
                reported |= names
        self.assertEqual(reported, set(FINDINGS))

    def test_one_set_reports_one_finding_list_whatever_order_its_lines_are_in(self) -> None:
        documents = [
            receipt(receipt_id="node-a", ancestors=[reference("ghost-1"), reference("node-b"), reference("node-b")]),
            receipt(receipt_id="node-b", ancestors=[reference("node-a")]),
            receipt(receipt_id="wave-1", receipt_kind=WAVE, ancestors=[reference("node-a", kind="probe-qualification")]),
        ]
        first = self.check_graph(documents, name="forward")
        second = self.check_graph(list(reversed(documents)), name="reversed")
        self.assertEqual(first["findings"], second["findings"])
        self.assertGreater(len(first["findings"]), 1)


class IterativeWalkTests(EnvelopeCase):
    """A receipt chain is as long as a mission is old, so the cycle walk may not recurse."""

    #: Five times CPython's default recursion limit: a recursive walk cannot reach the end of this.
    DEPTH = 5000

    def test_a_deep_acyclic_chain_is_clean_rather_than_a_recursion_error(self) -> None:
        self.assertGreater(self.DEPTH, sys.getrecursionlimit(), "the chain must exceed the recursion limit")
        done = self.run_tool("check-graph", "--receipts", str(self.store_set("deep", chain(self.DEPTH))))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertNotIn(b"RecursionError", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)
        self.assert_clean(json.loads(done.stdout), self.DEPTH)

    def test_a_loop_closed_at_the_far_end_of_a_deep_chain_is_found(self) -> None:
        """The positive control for the test above: the same depth, with one edge added, must still
        reach a verdict AND must actually find the loop rather than run out of stack looking."""
        path = self.store_set("deep-loop", chain(self.DEPTH, close_the_loop=True))
        done = self.run_tool("check-graph", "--receipts", str(path))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertNotIn(b"RecursionError", done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result["verdict"], GRAPH_DEFECTIVE)
        found = self.findings_named(result, "cyclic")
        self.assertEqual(len(found), 1)
        self.assertEqual(len(found[0]["implicated_receipt_ids"]), self.DEPTH)


class GraphRefusalTests(EnvelopeCase):
    """A set with one unadmittable member is not a graph, and no finding is derived from it."""

    def test_one_malformed_line_refuses_the_whole_set_and_derives_no_finding(self) -> None:
        documents = [
            receipt(receipt_id="node-a", ancestors=[reference("ghost-1")]),
            receipt(receipt_id="node-b", receipt_kind="not-a-family"),
        ]
        result = self.check_graph(documents)
        self.assert_refused(result, "the receipt on line 2")
        self.assertIsNone(result["receipts_checked"])
        self.assertIsNone(result["resolution_checked"])
        # POSITIVE CONTROL: with line 2 admissible the SAME set reports its dangling reference, so
        # the empty finding list above is the unadmitted-member rule and not a checker that gave up.
        documents[1] = receipt(receipt_id="node-b")
        control = self.check_graph(documents, name="control")
        self.assertEqual([item["finding"] for item in control["findings"]], ["dangling"])

    def test_a_refusal_names_the_line_that_carried_the_defect(self) -> None:
        documents = [receipt(receipt_id="node-a"), receipt(receipt_id="node-b"), receipt(receipt_id="Node-C")]
        result = self.check_graph(documents)
        joined = " | ".join(result["reasons"])
        self.assertIn("line 3", joined)
        self.assertNotIn("line 1", joined)
        self.assertNotIn("line 2", joined)


class CanonicalFormTests(EnvelopeCase):
    """The emitted bytes, asserted as BYTES. A parsed round-trip cannot see any of this."""

    def test_the_result_document_is_canonical_bytes_with_one_trailing_newline(self) -> None:
        done = self.run_tool("verify", "--receipt", str(self.store("receipt", receipt())))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)))
        self.assertTrue(done.stdout.endswith(b"}\n"))
        self.assertEqual(done.stdout.count(b"\n"), 1)
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))

    def test_a_non_ascii_body_value_is_escaped_in_the_emitted_bytes_and_in_the_digest(self) -> None:
        """`ensure_ascii=True` is the half of the canonical form a JSON round-trip cannot detect."""
        note = "clôture la tranche 6 — π \U0001f331"
        body = {"schema": "agentic-sdlc/wave-node-attempt-payload@1", "note": note}
        done = self.run_tool("verify", "--receipt", str(self.store("utf8", receipt(body=body))))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))
        result = json.loads(done.stdout)
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])
        # The digest is over the ESCAPED bytes, which is why a Python-side sha256 over the same
        # canonical form agrees with it and a UTF-8 encoding of the same value would not.
        self.assertEqual(result["content_digest"], expected_digest(body))
        self.assertIn(b"cl\\u00f4ture", canonical(body))  # o-circumflex, escaped
        self.assertNotIn(note.encode("utf-8"), canonical(body), "no raw UTF-8 may reach the digested bytes")
        self.assertNotEqual(result["content_digest"], self.verify(receipt(), name="ascii")["content_digest"])

    def test_every_verdict_carries_the_same_key_set(self) -> None:
        verified = self.verify(receipt(), name="ok")
        clean = self.check_graph([receipt()], name="clean")
        defective = self.check_graph([receipt(ancestors=[reference("ghost-1")])], name="defective")
        refused = self.verify(receipt(receipt_kind="not-a-family"), name="bad")
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(clean["verdict"], GRAPH_CLEAN)
        self.assertEqual(defective["verdict"], GRAPH_DEFECTIVE)
        self.assertEqual(refused["verdict"], REFUSED)
        for other in (clean, defective, refused):
            self.assertEqual(sorted(verified), sorted(other))
            self.assertEqual(
                [item["slug"] for item in verified["checks"]], [item["slug"] for item in other["checks"]]
            )
        for document in (verified, clean, defective, refused):
            self.assertEqual(document["exit_code"], EXIT_OK)
            self.assertEqual(document["schema"], RESULT_SCHEMA)
            self.assertGreater(len(document["consequence"]), 60)
            self.assertGreater(len(document["residuals"]), 3)

    def test_the_reasons_list_is_exactly_the_checks_reasons(self) -> None:
        result = self.verify(receipt(receipt_kind="not-a-family", emitting_plane="Claude"), name="two")
        flat = [reason for item in result["checks"] for reason in item["reasons"]]
        self.assertEqual(result["reasons"], flat)
        self.assertGreater(len(result["reasons"]), 1, "two broken fields must both be named")
        for item in result["checks"]:
            self.assertEqual(item["met"], not item["reasons"])


class MalformedInputTests(EnvelopeCase):
    """Exit 2 is reserved for input that cannot be read as receipt documents: the question, not the
    answer, was unusable. Everything about a receipt's CONTENT is a named refusal at exit 0."""

    def assert_input_error(self, *argv: str) -> bytes:
        done = self.run_tool(*argv)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"", "an input error must emit no result document")
        return done.stderr

    def test_an_absent_receipt_file_is_malformed_input(self) -> None:
        # POSITIVE CONTROL: a present file at the same kind of path is exit 0.
        self.assert_verified(receipt())
        err = self.assert_input_error("verify", "--receipt", str(self.work / "no-such-file.json"))
        self.assertIn(b"cannot read the receipt", err)

    def test_a_directory_supplied_as_a_receipt_is_malformed_input(self) -> None:
        (self.work / "adir").mkdir()
        self.assertIn(b"not a regular file", self.assert_input_error("verify", "--receipt", str(self.work / "adir")))

    def test_a_file_that_is_not_json_is_malformed_input(self) -> None:
        path = self.store_bytes("broken.json", b"{not json")
        self.assertIn(b"is not JSON", self.assert_input_error("verify", "--receipt", str(path)))

    def test_a_file_that_is_not_a_json_object_is_malformed_input(self) -> None:
        path = self.store_bytes("list.json", b"[]\n")
        self.assertIn(b"not a JSON object", self.assert_input_error("verify", "--receipt", str(path)))

    def test_a_duplicate_json_key_is_refused_rather_than_silently_resolved(self) -> None:
        raw = json.dumps(receipt()).replace('"receipt_id": "node-a"', '"receipt_id": "node-a", "receipt_id": "node-b"', 1)
        if '"receipt_id": "node-b"' not in raw:  # separators differ by dumps flavour
            raw = json.dumps(receipt()).replace('"receipt_id":"node-a"', '"receipt_id":"node-a","receipt_id":"node-b"', 1)
        path = self.store_bytes("dupe.json", raw.encode("utf-8"))
        self.assertIn(b"repeats the JSON key", self.assert_input_error("verify", "--receipt", str(path)))

    def test_a_non_finite_json_constant_is_malformed_input(self) -> None:
        path = self.store_bytes("nan.json", b'{"body": {"usage": NaN}}\n')
        self.assertIn(b"non-finite JSON constant", self.assert_input_error("verify", "--receipt", str(path)))

    def test_a_number_that_overflows_to_infinity_is_malformed_input(self) -> None:
        """`parse_constant` never sees `1e400`: the float parser overflows it to `inf` silently, and
        `inf` would then reach the canonical encoder as a `ValueError` inside the digest."""
        # POSITIVE CONTROL: the same body with a finite number of the same shape is admitted.
        finite = receipt(body={"schema": "agentic-sdlc/wave-node-attempt-payload@1", "usage": 1e30})
        self.assert_verified(finite, name="finite")
        path = self.store_bytes("inf.json", b'{"body": {"usage": 1e400}}\n')
        self.assertIn(b"non-finite number", self.assert_input_error("verify", "--receipt", str(path)))

    def test_an_overflowed_number_inside_an_otherwise_valid_receipt_is_malformed_input(self) -> None:
        """The expensive half of the same guard: an admitted body reaches the canonical encoder, where
        `inf` is a `ValueError` the digest derivation would raise as a traceback and exit 1."""
        finite = receipt(body={"schema": "agentic-sdlc/wave-node-attempt-payload@1", "usage": 1e30})
        # POSITIVE CONTROL: the finite receipt verifies, so the refusal below is about the number.
        self.assert_verified(finite, name="finite")
        raw = json.dumps(finite)
        self.assertIn("1e+30", raw)
        path = self.store_bytes("valid-inf.json", raw.replace("1e+30", "1e400").encode("utf-8"))
        err = self.assert_input_error("verify", "--receipt", str(path))
        self.assertIn(b"non-finite number", err)
        self.assertNotIn(b"Traceback", err, "a non-finite number is a classified input error")

    def test_a_negative_overflow_is_malformed_input(self) -> None:
        path = self.store_bytes("neginf.json", b'{"body": {"usage": -1e400}}\n')
        self.assertIn(b"non-finite number", self.assert_input_error("verify", "--receipt", str(path)))

    def test_a_non_finite_number_nested_deep_inside_the_body_is_malformed_input(self) -> None:
        """The walk over parsed values is not a top-level check: a receipt body is a family payload
        and the number that overflowed may be anywhere inside it."""
        path = self.store_bytes("deep-inf.json", b'{"body": {"a": [{"b": [[{"c": 1e400}]]}]}}\n')
        self.assertIn(b"non-finite number", self.assert_input_error("verify", "--receipt", str(path)))

    def test_non_utf8_bytes_are_malformed_input(self) -> None:
        path = self.store_bytes("latin.json", b'{"body": {"note": "caf\xe9"}}\n')
        self.assertIn(b"is not UTF-8 text", self.assert_input_error("verify", "--receipt", str(path)))

    def test_json_nested_deeper_than_the_decoder_admits_is_malformed_input(self) -> None:
        """The depth is DERIVED from this interpreter's own recursion limit, with the same 20x
        headroom the original fixed 20000-deep payload carried over CPython's default limit of
        1000, so the fixture stays deep enough to fail on any CPython rather than passing on a
        newer one whose decoder or default limit moved -- which is exactly what let a fixed 20000
        parse cleanly on Python 3.14+."""
        depth = 20 * sys.getrecursionlimit()
        payload = b'{"body": {"a": ' + b"[" * depth + b"]" * depth + b"}}\n"
        err = self.assert_input_error("verify", "--receipt", str(self.store_bytes("nest.json", payload)))
        self.assertIn(b"nests JSON deeper", err)
        self.assertNotIn(b"Traceback", err, "a recursion limit is a classified input error, not a traceback")

    def test_a_blank_line_in_a_receipt_set_is_malformed_input(self) -> None:
        path = self.store_set("blank", [receipt()])
        path.write_text(path.read_text(encoding="utf-8") + "\n" + json.dumps(receipt(receipt_id="node-b")) + "\n",
                        encoding="utf-8")
        err = self.assert_input_error("check-graph", "--receipts", str(path))
        self.assertIn(b"line 2", err)
        self.assertIn(b"is blank", err)

    def test_an_empty_receipt_set_is_malformed_input_rather_than_a_clean_graph(self) -> None:
        path = self.store_bytes("empty.jsonl", b"")
        err = self.assert_input_error("check-graph", "--receipts", str(path))
        self.assertIn(b"carries no receipt document", err)

    def test_a_receipt_set_line_that_is_not_an_object_is_malformed_input(self) -> None:
        path = self.store_bytes("badline.jsonl", json.dumps(receipt()).encode("utf-8") + b'\n"just a string"\n')
        err = self.assert_input_error("check-graph", "--receipts", str(path))
        self.assertIn(b"line 2", err)
        self.assertIn(b"not a JSON object", err)

    def test_a_grammar_error_is_exit_two_and_writes_no_result_document(self) -> None:
        self.assert_input_error("verify", "--not-a-flag")
        self.assert_input_error()
        self.assert_input_error("verify")  # --receipt is required
        self.assert_input_error("check-graph")  # --receipts is required
        self.assert_input_error("check-graph", "--receipt", str(self.store("receipt", receipt())))


class ExitSpaceTests(EnvelopeCase):
    """The module's exit space is 0, 2, and 1, and it says WHY 3 and 4 are unreachable."""

    def test_the_module_declares_why_three_and_four_are_absent(self) -> None:
        collapsed = " ".join(TOOL.read_text(encoding="utf-8").split())
        self.assertIn("a tool that can cause no effect can neither refuse before one nor admit one", collapsed)
        done = self.run_tool("verify", "--help")
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertIn("3 and 4 do not apply", " ".join(done.stdout.decode("utf-8").split()))

    def test_a_refusal_and_a_finding_are_both_derived_results_and_therefore_exit_zero(self) -> None:
        refused = self.run_tool("verify", "--receipt", str(self.store("bad", receipt(receipt_kind="nope"))))
        self.assertEqual(refused.returncode, EXIT_OK)
        self.assertEqual(json.loads(refused.stdout)["verdict"], REFUSED)
        defective = self.run_tool(
            "check-graph", "--receipts", str(self.store_set("bad", [receipt(ancestors=[reference("ghost-1")])]))
        )
        self.assertEqual(defective.returncode, EXIT_OK)
        self.assertEqual(json.loads(defective.stdout)["verdict"], GRAPH_DEFECTIVE)

    def test_the_tool_runs_no_subprocess_and_opens_nothing_for_writing(self) -> None:
        """The reason 3 and 4 are unreachable, checked rather than asserted in prose.

        Read with `ast` and not `in`: the module docstring says "subprocess-free", so a substring
        search over the source would find the word it is promising the absence of.
        """
        modules, calls = imports_and_calls(TOOL)
        self.assertEqual(
            modules,
            {"__future__", "argparse", "collections", "hashlib", "json", "pathlib", "re", "stat", "sys", "typing"},
            "an effect-free tool imports only the standard parsing and display surface",
        )
        forbidden = {"open", "write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename",
                     "symlink_to", "hardlink_to", "chmod", "system", "popen", "fdopen", "fsync"}
        self.assertEqual(calls & forbidden, set(), "an effect-free tool calls nothing that can write")
        # POSITIVE CONTROL: the same walk over a tool that DOES write finds both classes, so these
        # assertions are about the source rather than about names that appear nowhere in this repo.
        other_modules, other_calls = imports_and_calls(CONTROL_TOOL)
        self.assertIn("os", other_modules)
        self.assertTrue(other_calls & forbidden, "the control tool must exercise the forbidden set")

    def test_no_compiled_pattern_uses_a_unicode_digit_or_word_class(self) -> None:
        """`\\d` and `\\w` admit every Unicode decimal digit, which is how an Arabic-Indic instant or
        receipt id would be accepted as an ASCII-looking identity. Every class must be explicit.

        Read with `ast` over the compiled PATTERNS and not with `in` over the source: the tool's own
        docstring explains why it never writes those classes, and a substring search would fail on
        the explanation.
        """
        patterns = compiled_patterns(TOOL.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(patterns), 3, "the extraction found no compiled pattern to check")
        for pattern in patterns:
            for banned in ("\\d", "\\w"):
                self.assertNotIn(banned, pattern, f"{banned} admits Unicode digits; write the class out")
        self.assertTrue(any("[0-9]" in pattern for pattern in patterns), patterns)
        self.assertTrue(any("[a-z0-9]" in pattern for pattern in patterns), patterns)
        # POSITIVE CONTROL: the same extraction over a source that DOES use one finds it, so the loop
        # above is asserting over real pattern strings rather than over an empty list.
        control = compiled_patterns('import re\n_BAD = re.compile(r"\\d{4}")\n')
        self.assertEqual(len(control), 1)
        self.assertIn("\\d", control[0])


class HostileDescriptorTests(EnvelopeCase):
    """A display channel may cost its line; the result document may not be silently lost."""

    def test_a_closed_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        argv = ["verify", "--receipt", str(self.work / "no-such-file.json")]
        # POSITIVE CONTROL: with an ordinary stderr the same run exits 2 and says so.
        control = self.run_tool(*argv)
        self.assertEqual(control.returncode, EXIT_INPUT)
        self.assertIn(b"cannot read the receipt", control.stderr)
        code, out = run_with_hostile_stderr([sys.executable, "-B", str(TOOL), *argv], mode="closed", cwd=self.work)
        self.assertEqual(code, EXIT_INPUT, "a missing stderr must not become exit 1")
        self.assertEqual(out, b"", "an input error must emit no result document, even with no stderr")

    def test_an_epipe_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        argv = ["verify", "--receipt", str(self.work / "no-such-file.json")]
        code, out = run_with_hostile_stderr([sys.executable, "-B", str(TOOL), *argv], mode="epipe", cwd=self.work)
        self.assertEqual(code, EXIT_INPUT, "a broken stderr must not become exit 120")
        self.assertEqual(out, b"")

    def test_a_grammar_error_with_no_stderr_puts_no_usage_on_stdout(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, out = run_with_hostile_stderr(
                    [sys.executable, "-B", str(TOOL), "verify", "--not-a-flag"], mode=mode, cwd=self.work
                )
                self.assertEqual(code, EXIT_INPUT)
                self.assertEqual(out, b"", "argparse must not fall back to stdout, where the document lives")

    def test_a_closed_stdout_reports_an_undelivered_document(self) -> None:
        argv = ["check-graph", "--receipts", str(self.store_set("set", [receipt()]))]
        # POSITIVE CONTROL: with an ordinary stdout the same run reports a clean graph.
        control = self.run_tool(*argv)
        self.assertEqual(control.returncode, EXIT_OK)
        self.assertEqual(json.loads(control.stdout)["verdict"], GRAPH_CLEAN)
        code, err = run_with_hostile_stdout([sys.executable, "-B", str(TOOL), *argv], mode="closed", cwd=self.work)
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn(b"handed no stdout", err)

    def test_an_epipe_stdout_reports_an_undelivered_document(self) -> None:
        argv = ["verify", "--receipt", str(self.store("receipt", receipt()))]
        code, err = run_with_hostile_stdout([sys.executable, "-B", str(TOOL), *argv], mode="epipe", cwd=self.work)
        self.assertEqual(code, EXIT_INTERNAL, "a broken stdout must not become exit 120")
        self.assertIn(b"not delivered", err)

    def test_help_with_no_stdout_exits_cleanly_instead_of_crashing(self) -> None:
        control = self.run_tool("check-graph", "--help")
        self.assertEqual(control.returncode, EXIT_OK)
        self.assertIn(b"--receipts", control.stdout)
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, _ = run_with_hostile_stdout(
                    [sys.executable, "-B", str(TOOL), "check-graph", "--help"], mode=mode, cwd=self.work
                )
                self.assertEqual(code, EXIT_OK)

    def test_both_streams_hostile_at_once_still_classifies(self) -> None:
        argv = ["verify", "--receipt", str(self.store("receipt", receipt()))]
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&- 2>&-; exec "$@"', "sh", sys.executable, "-B", str(TOOL), *argv],
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_INTERNAL)

    def test_both_streams_epipe_at_once_still_classifies(self) -> None:
        argv = [sys.executable, "-B", str(TOOL), "verify", "--receipt", str(self.store("receipt", receipt()))]
        out_read, out_write = os.pipe()
        err_read, err_write = os.pipe()
        os.close(out_read)
        os.close(err_read)
        try:
            child = subprocess.Popen(
                argv, stdout=out_write, stderr=err_write, cwd=str(self.work), env=constructed_environment()
            )
        finally:
            os.close(out_write)
            os.close(err_write)
        self.assertEqual(child.wait(), EXIT_INTERNAL, "two broken streams must not become exit 120")


class EnvironmentAndCwdTests(EnvelopeCase):
    """The tool reads no environment variable, and its verdict does not move with the directory."""

    def test_the_tool_reads_no_environment_variable(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)
        # POSITIVE CONTROL: the same grep over a tool that DOES read one finds it.
        self.assertIn("os.environ", CONTROL_TOOL.read_text(encoding="utf-8"))

    def test_a_verdict_does_not_change_when_an_unrelated_variable_is_set(self) -> None:
        argv = [sys.executable, "-B", str(TOOL), "verify", "--receipt", str(self.store("receipt", receipt()))]
        first = subprocess.run(argv, capture_output=True, cwd=str(self.work), check=False,
                               env=constructed_environment())
        second = subprocess.run(
            argv,
            capture_output=True,
            cwd=str(self.work),
            check=False,
            env=constructed_environment(
                {"AGENTIC_SDLC_RECEIPT_ENVELOPE": "verified", "TZ": "Pacific/Kiritimati", "SOURCE_DATE_EPOCH": "0"}
            ),
        )
        self.assertEqual(first.returncode, EXIT_OK)
        self.assertEqual(second.stdout, first.stdout)

    def test_a_verdict_does_not_change_with_the_working_directory(self) -> None:
        path = self.store("receipt", receipt())
        nested = self.work / "a" / "deeply" / "nested" / "scratch"
        nested.mkdir(parents=True)
        argv = [sys.executable, "-B", str(TOOL), "verify", "--receipt", str(path)]
        here = subprocess.run(argv, capture_output=True, cwd=str(self.work), check=False,
                              env=constructed_environment())
        there = subprocess.run(argv, capture_output=True, cwd=str(nested), check=False,
                               env=constructed_environment())
        self.assertEqual(here.returncode, EXIT_OK, here.stderr.decode("utf-8", "replace"))
        self.assertEqual(there.stdout, here.stdout)


if __name__ == "__main__":
    unittest.main()
