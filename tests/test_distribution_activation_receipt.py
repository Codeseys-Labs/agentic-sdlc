"""Tests for the `distribution-activation@1` receipt body: the first producer body of the family.

Nine kinds of test live here, and they check different things.

The ROUND-TRIP tests seal an observation, validate the result, and then hand the SAME bytes to the
skills-plane `receipt-envelope.py` checker as an INDEPENDENT verifier. That last step is the point:
this producer re-expresses the envelope's schema string, kinds, and relations rather than importing
them, so a test that only asked this module whether its own output was well-formed would prove
nothing about the envelope it claims to fill.

The DRIFT tests read the skills-plane source with `ast` -- parsing, never importing, because the
no-cross-plane-import rule applies to the tests' subject and not only to the module -- and assert the
re-expressed envelope schema, the six kinds, and the six relations are identical. Re-expression's
whole cost is drift, and this is where it is paid.

The CLOSED-VOCABULARY tests walk each closed set and assert both halves: a member is admitted and a
near-miss is refused by name. Every negative case carries a POSITIVE CONTROL in the same test -- the
unmutated document is asserted to reach `sealed` FIRST -- so a test that stopped exercising its guard
would also have to stop reaching that verdict.

The TRICHOTOMY tests are the ones that would silently pass under a `.get(key)` implementation: for
one field they assert three DIFFERENT outcomes for absent, null, and empty-string, and they assert the
reasons differ, because "supplied and lost" and "never supplied" are different defects.

The UNKNOWN-CONSULTING tests attack the defect class where an admission check reads only the recorded
facts. `effect_state: complete` beside a named unknown must refuse, and the control in the same test
shows the identical document admits once the unknown is gone.

The PRODUCER-HOIST test is the one that catches a dict-literal evaluation-order bug: an entry whose
content digest is null must come back with an entry-content unknown NAMING it, which is exactly the
record a literal that read `unknowns` before walking the entries would drop.

The RENDERING tests assert control characters never reach a rendered line while the STORED value keeps
them verbatim, because a receipt records what was observed and a terminal is not a receipt.

The NON-FINITE tests use `1e400`, which `parse_constant` never sees -- `json` overflows it to `inf`
inside the float parser -- and each carries a finite control proving the exit code came from the
overflow and not from the surrounding document.

The GRAPH-INTEROP tests build a two-receipt set and let the skills-plane `check-graph` resolve it, then
show the shape-versus-graph split directly: a self-naming ancestor reference is admitted by this
module (a graph FINDING is not a shape defect) and reported as `cyclic` by the checker that owns it.
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
sys.path.insert(0, str(ROOT))

from scripts import distribution_activation_receipt as dar  # noqa: E402

MODULE = ROOT / "scripts" / "distribution_activation_receipt.py"
ENVELOPE_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "receipt-envelope.py"

BODY_SCHEMA = "agentic-sdlc/distribution-activation-body@1"
ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"
RESULT_SCHEMA = "agentic-sdlc/distribution-activation-result@1"
RECEIPT_KIND = "distribution-activation"

SEALED = "sealed"
VALIDATED = "validated"
REFUSED = "refused"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The six receipt families and six relations, spelled out here rather than imported from the module
#: under test, so a vocabulary this module quietly widened would fail rather than agree with itself.
KINDS = (
    "distribution-activation",
    "incident-recovery",
    "integration-completion",
    "probe-qualification",
    "route-credential-lifecycle",
    "workflow-wave-node-attempt",
)
RELATIONS = (
    "contained-by",
    "derived-from",
    "references-evidence",
    "remediates",
    "retries",
    "supersedes",
)

#: Deletes a key from a builder's output, so a test can say "this field was never supplied" and mean
#: something different from "this field is null".
DROP = object()


def hexof(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def entry(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "content_sha256": hexof("entry"),
        "disposition": "installed",
        "entry_name": "skills/agentic-sdlc",
        "prestate": "absent",
    }
    record.update(overrides)
    return {key: value for key, value in record.items() if value is not DROP}


FOREIGN_ENTRY = entry(
    content_sha256=hexof("foreign"),
    disposition="preserved",
    entry_name="skills/foreign-thing",
    prestate="foreign",
)


def body(**overrides: Any) -> dict[str, Any]:
    """A body that seals clean, with every field overridable and any field deletable via DROP."""
    value: dict[str, Any] = {
        "activation_scope": "user-plane",
        "archive_sha256": hexof("archive"),
        "candidate_id": hexof("candidate"),
        "effect_state": "complete",
        "entries": [entry(), FOREIGN_ENTRY],
        "host": "claude",
        "journal_sha256": hexof("journal"),
        "operation": "install",
        "plan_sha256": hexof("plan"),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "requested_version": "0.6.3",
        "resolved_version": "0.6.3",
        "schema_version": BODY_SCHEMA,
        "terminal_phase": "activated",
        "unknowns": [],
        "version_source": "adapter-readback",
    }
    value.update(overrides)
    return {key: item for key, item in value.items() if item is not DROP}


ACQUISITION_REFERENCE = {
    "expected_kind": RECEIPT_KIND,
    "receipt_id": "acquisition-1",
    "relation": "derived-from",
}


def document(body_value: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "ancestors": [dict(ACQUISITION_REFERENCE)],
        "body": body() if body_value is None else body_value,
        "content_digest": "",
        "emitting_plane": "repository-gate",
        "receipt_id": "activation-1",
        "receipt_kind": RECEIPT_KIND,
        "schema": ENVELOPE_SCHEMA,
        "stated_at": "2026-08-20T12:00:00Z",
    }
    value.update(overrides)
    return {key: item for key, item in value.items() if item is not DROP}


def seal(doc: dict[str, Any]) -> dict[str, Any]:
    return dar.derive("seal", doc, "the observation")


def validate(doc: dict[str, Any]) -> dict[str, Any]:
    return dar.derive("validate", doc, "the receipt")


def sealed(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """The receipt from a successful seal, asserting the seal succeeded on the way past."""
    result = seal(document() if doc is None else doc)
    if result["verdict"] != SEALED:
        raise AssertionError(f"fixture did not seal: {result['reasons']}")
    receipt = result["receipt"]
    assert isinstance(receipt, dict)
    return receipt


def reasons_text(result: dict[str, Any]) -> str:
    return "\n".join(result["reasons"])


def run_module(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MODULE), *args],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )


def run_envelope(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENVELOPE_TOOL), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def write_json(directory: str, name: str, value: Any) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(value))
    return path


def skills_plane_constant(name: str) -> Any:
    """Read one module-level constant out of the skills-plane source by PARSING it.

    Deliberately not an import: the no-cross-plane-import rule is the thing under test, and a test
    that imported the tool to check the module did not would be asserting the opposite of the rule.
    """
    tree = ast.parse(ENVELOPE_TOOL.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"the skills-plane envelope declares no module-level {name}")


class RoundTrip(unittest.TestCase):
    """Seal, validate, and let the tool that owns the envelope verify the same bytes."""

    def test_seal_then_validate_then_envelope_verify(self) -> None:
        result = seal(document())
        self.assertEqual(result["verdict"], SEALED, result["reasons"])
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        receipt = result["receipt"]
        self.assertEqual(validate(receipt)["verdict"], VALIDATED)
        with tempfile.TemporaryDirectory() as directory:
            path = write_json(directory, "receipt.json", receipt)
            proof = run_envelope("verify", "--receipt", path)
            self.assertEqual(proof.returncode, EXIT_OK, proof.stderr)
            self.assertEqual(json.loads(proof.stdout)["verdict"], "verified", proof.stdout)

    def test_record_seal_is_over_the_body_minus_its_own_digest(self) -> None:
        receipt = sealed()
        payload = receipt["body"]
        without = {key: value for key, value in payload.items() if key != "record_sha256"}
        expected = hashlib.sha256(
            json.dumps(
                without, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
            ).encode("utf-8")
            + b"\n"
        ).hexdigest()
        self.assertEqual(payload["record_sha256"], expected)
        # POSITIVE CONTROL for the "minus its own digest" half: sealing the WHOLE body, record digest
        # included, is a different value, so the test above cannot be passing by accident.
        including = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
            ).encode("utf-8")
            + b"\n"
        ).hexdigest()
        self.assertNotEqual(including, expected)
        self.assertEqual(receipt["content_digest"], including)

    def test_canonical_form_is_bytes_not_a_parsed_value(self) -> None:
        payload = {"z": 1, "a": "é"}
        self.assertEqual(dar.canonical_bytes(payload), b'{"a":"\\u00e9","z":1}\n')
        # POSITIVE CONTROL: a JSON round-trip cannot see the ensure_ascii half at all.
        self.assertEqual(json.loads(dar.canonical_bytes(payload).decode("ascii")), payload)

    def test_a_tampered_body_breaks_both_seals(self) -> None:
        receipt = sealed()
        self.assertEqual(validate(receipt)["verdict"], VALIDATED)  # positive control
        tampered = json.loads(json.dumps(receipt))
        tampered["body"]["resolved_version"] = "9.9.9"
        result = validate(tampered)
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("record_sha256", reasons_text(result))
        self.assertIn("content_digest", reasons_text(result))

    def test_seal_refuses_to_reseal_a_sealed_receipt(self) -> None:
        receipt = sealed()
        result = seal(receipt)
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("already carries a content_digest", reasons_text(result))
        self.assertIsNone(result["receipt"])

    def test_a_refused_seal_emits_no_receipt_at_all(self) -> None:
        result = seal(document(body(host="all")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIsNone(result["receipt"])
        self.assertIsNone(result["record_sha256"])
        self.assertIsNone(result["content_digest"])
        self.assertEqual(result["rendered"], [])
        # POSITIVE CONTROL: the same shape with an admitted host does produce all four.
        clean = seal(document())
        self.assertIsNotNone(clean["receipt"])
        self.assertIsNotNone(clean["record_sha256"])
        self.assertIsNotNone(clean["content_digest"])
        self.assertTrue(clean["rendered"])


class EnvelopeDrift(unittest.TestCase):
    """The re-expressed envelope vocabularies must equal the skills plane's, or re-expression lied."""

    def test_envelope_schema_string_matches_the_skills_plane(self) -> None:
        self.assertEqual(dar.ENVELOPE_SCHEMA, skills_plane_constant("ENVELOPE_SCHEMA"))

    def test_receipt_kinds_match_the_skills_plane(self) -> None:
        self.assertEqual(tuple(dar.RECEIPT_KINDS), tuple(skills_plane_constant("RECEIPT_KINDS")))
        self.assertEqual(tuple(dar.RECEIPT_KINDS), KINDS)

    def test_relations_match_the_skills_plane(self) -> None:
        self.assertEqual(tuple(dar.RELATIONS), tuple(skills_plane_constant("RELATIONS")))
        self.assertEqual(tuple(dar.RELATIONS), RELATIONS)

    def test_this_kind_is_one_of_the_six_closed_kinds(self) -> None:
        self.assertIn(dar.RECEIPT_KIND, skills_plane_constant("RECEIPT_KINDS"))
        # POSITIVE CONTROL: the membership assertion above can fail.
        self.assertNotIn("distribution-install", skills_plane_constant("RECEIPT_KINDS"))

    def test_the_family_relations_are_a_subset_of_the_envelope_vocabulary(self) -> None:
        self.assertTrue(set(dar.FAMILY_RELATIONS).issubset(set(dar.RELATIONS)))
        self.assertNotIn("contained-by", dar.FAMILY_RELATIONS)

    def test_the_module_imports_nothing_from_the_skills_plane(self) -> None:
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for name in imported:
            self.assertNotIn("skills", name)
            self.assertNotIn("receipt_envelope", name)
        # POSITIVE CONTROL: the walk really does see this module's imports.
        self.assertIn("hashlib", imported)
        self.assertIn("json", imported)


def resealed(body_value: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """A document whose two seals are correct for an ARBITRARY body.

    `seal` normalises an observation before it checks it, which is what a producer must do; this
    builder skips that step so a `validate` test can exercise a body check without the seal reasons
    drowning out the one it is about.
    """
    payload = dar.seal_body(body_value)
    return document(
        payload,
        content_digest=dar.envelope_content_digest(payload, "the receipt"),
        **overrides,
    )


def partial_body(**overrides: Any) -> dict[str, Any]:
    """A body whose effect state admits a named unknown, for the tests that need one."""
    value = {"effect_state": "partial", "terminal_phase": "activated-partial"}
    value.update(overrides)
    return body(**value)


class SealsClean(unittest.TestCase):
    """A base whose `setUp` is a POSITIVE CONTROL for every negative test in the class.

    Each subclass asserts that some hostile document is REFUSED, and the failure mode of such a test
    is passing because everything is refused -- a broken fixture, a check that fires on the base
    document, a verdict wired to a constant. Asserting the unmutated fixture reaches `sealed` before
    every single test makes that failure mode impossible to hide: a guard that stopped working can no
    longer be indistinguishable from a pipeline that refuses everything.
    """

    def setUp(self) -> None:
        control = seal(document())
        self.assertEqual(control["verdict"], SEALED, control["reasons"])


ARCHIVE_UNKNOWN = {
    "detail": "the archive was streamed and never landed as a file, so no digest was taken",
    "observation": "archive-digest",
    "subject": "archive_sha256",
}


class ClosedBodySet(SealsClean):
    def test_an_unknown_body_field_is_refused_not_ignored(self) -> None:
        self.assertEqual(seal(document())["verdict"], SEALED)  # positive control
        result = seal(document(body(activation_note="tidy")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("activation_note", reasons_text(result))

    def test_every_required_body_field_is_required(self) -> None:
        for key in dar.BODY_KEYS:
            with self.subTest(key=key):
                result = seal(document(body(**{key: DROP})))
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn(f"carries no {key}", reasons_text(result))

    def test_a_wrong_body_schema_version_is_refused(self) -> None:
        result = seal(document(body(schema_version="agentic-sdlc/distribution-activation-body@2")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("declares schema_version", reasons_text(result))

    def test_an_unknown_envelope_field_is_refused(self) -> None:
        result = seal(document(note="hello"))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("unknown envelope field", reasons_text(result))

    def test_another_receipt_kind_is_refused_by_this_producer(self) -> None:
        result = seal(document(receipt_kind="probe-qualification"))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("this producer writes exactly", reasons_text(result))

    def test_a_non_object_body_is_refused_without_a_traceback(self) -> None:
        result = seal(document("not-a-body"))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("not a agentic-sdlc/distribution-activation-body@1 object", reasons_text(result))


class ClosedVocabularies(SealsClean):
    """The vocabularies are pinned by exact membership, not only consumed by other checks.

    Without these, widening OPERATIONS or PRESTATES survives the whole suite while the unguarded
    OPERATION_PHASES / PRESTATE_DISPOSITIONS lookups turn the named refusal into a raw KeyError.
    """

    def test_every_vocabulary_member_has_a_row_in_every_table_that_reads_it(self) -> None:
        self.assertEqual(set(dar.OPERATIONS), set(dar.OPERATION_DISPOSITIONS))
        self.assertEqual(set(dar.OPERATIONS), set(dar.OPERATION_PHASES))
        self.assertEqual(set(dar.PRESTATES), set(dar.PRESTATE_DISPOSITIONS))

    def test_the_operation_and_prestate_vocabularies_are_exactly_the_decided_sets(self) -> None:
        self.assertEqual(set(dar.OPERATIONS), {"install", "uninstall", "update"})
        self.assertEqual(set(dar.PRESTATES), {"absent", "foreign", "modified", "owned"})

    def test_refresh_is_refused_naming_the_closed_vocabulary(self) -> None:
        self.assertEqual(seal(document())["verdict"], SEALED)  # positive control
        result = seal(document(body(operation="refresh")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("'refresh'", reasons_text(result))
        self.assertIn("closed vocabulary", reasons_text(result))


class PayloadIdentity(SealsClean):
    def test_version_source_request_is_refused_by_name(self) -> None:
        self.assertEqual(seal(document(body(version_source="archive-manifest")))["verdict"], SEALED)
        result = seal(document(body(version_source="request")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("agentic-sdlc-0faa", reasons_text(result))
        self.assertIn("never becomes readback", reasons_text(result))

    def test_an_unlisted_version_source_is_refused(self) -> None:
        result = seal(document(body(version_source="guessed")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("closed vocabulary", reasons_text(result))

    def test_a_null_resolved_version_is_refused_and_names_the_substitution(self) -> None:
        result = seal(document(body(resolved_version=None)))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("requested_version as the only version", reasons_text(result))

    def test_a_requested_version_may_differ_from_the_resolved_one(self) -> None:
        # Honest drift is RECORDED, not equalised: the two are separate facts.
        receipt = sealed(document(body(requested_version="0.6", resolved_version="0.6.3")))
        self.assertEqual(receipt["body"]["requested_version"], "0.6")
        self.assertEqual(receipt["body"]["resolved_version"], "0.6.3")

    def test_a_null_requested_version_is_admitted_as_no_request(self) -> None:
        receipt = sealed(document(body(requested_version=None)))
        self.assertIsNone(receipt["body"]["requested_version"])
        self.assertIn("no-version-requested", "\n".join(seal(document(body(requested_version=None)))["rendered"]))

    def test_a_unicode_digit_digest_is_refused(self) -> None:
        ascii_digest = hexof("candidate")
        self.assertEqual(seal(document(body(candidate_id=ascii_digest)))["verdict"], SEALED)
        unicode_digest = "٩" + ascii_digest[1:]
        self.assertEqual(len(unicode_digest), 64)
        self.assertTrue(unicode_digest[0].isdigit())  # \d would match this character
        result = seal(document(body(candidate_id=unicode_digest)))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("[0-9a-f]", reasons_text(result))

    def test_a_null_candidate_id_has_no_honest_unknown(self) -> None:
        result = seal(document(body(candidate_id=None)))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("no honest unknown", reasons_text(result))


class HostAndScope(SealsClean):
    def test_the_host_is_claude_and_a_wildcard_is_refused_by_name(self) -> None:
        self.assertEqual(seal(document(body(host="claude")))["verdict"], SEALED)
        for hostile in ("all", "*", "claude-*"):
            with self.subTest(host=hostile):
                result = seal(document(body(host=hostile)))
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn("wildcard", reasons_text(result))

    def test_an_unobserved_host_is_refused_as_a_closed_vocabulary(self) -> None:
        result = seal(document(body(host="codex")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("closed vocabulary", reasons_text(result))

    def test_a_wildcard_scope_is_refused_even_when_it_is_a_well_formed_token(self) -> None:
        self.assertEqual(seal(document(body(activation_scope="user-plane")))["verdict"], SEALED)
        result = seal(document(body(activation_scope="all")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("wildcard", reasons_text(result))
        # POSITIVE CONTROL for "well-formed token": the token shape alone WOULD have admitted it.
        self.assertTrue(dar._TOKEN.match("all"))

    def test_an_uppercase_scope_is_refused_because_correlation_compares_literally(self) -> None:
        result = seal(document(body(activation_scope="User-Plane")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("lowercase ASCII token", reasons_text(result))


class EntryInventory(SealsClean):
    def test_a_foreign_entry_may_only_be_preserved_and_is_named(self) -> None:
        receipt = sealed()
        names = [row["entry_name"] for row in receipt["body"]["entries"]]
        self.assertIn("skills/foreign-thing", names)  # NAMED, never dropped
        result = seal(document(body(entries=[entry(), entry(**{**FOREIGN_ENTRY, "disposition": "installed"})])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("never adopted", reasons_text(result))

    def test_a_modified_entry_may_only_be_preserved(self) -> None:
        result = seal(document(body(entries=[entry(prestate="modified", disposition="refreshed")])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("admits only ['preserved']", reasons_text(result))
        control = seal(document(body(entries=[entry(prestate="modified", disposition="preserved")])))
        self.assertEqual(control["verdict"], SEALED, control["reasons"])

    def test_a_repeated_entry_name_is_refused(self) -> None:
        result = seal(document(body(entries=[entry(), entry()])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("repeats the entry_name", reasons_text(result))

    def test_a_traversal_segment_in_an_entry_name_is_refused(self) -> None:
        result = seal(document(body(entries=[entry(entry_name="skills/../../etc/passwd")])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("'..'", reasons_text(result))

    def test_a_removed_entry_carries_no_content_digest(self) -> None:
        uninstall = body(
            operation="uninstall",
            terminal_phase="retired",
            entries=[entry(prestate="owned", disposition="removed", content_sha256=None)],
        )
        self.assertEqual(seal(document(uninstall))["verdict"], SEALED)
        hostile = body(
            operation="uninstall",
            terminal_phase="retired",
            entries=[entry(prestate="owned", disposition="removed", content_sha256=hexof("gone"))],
        )
        result = seal(document(hostile))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("nothing remains", reasons_text(result))

    def test_an_uninstall_may_not_record_an_installed_entry(self) -> None:
        result = seal(
            document(
                body(
                    operation="uninstall",
                    terminal_phase="retired",
                    entries=[entry(prestate="absent", disposition="installed")],
                )
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("that operation admits only ['preserved', 'removed']", reasons_text(result))

    def test_an_install_may_not_record_a_removed_entry(self) -> None:
        result = seal(document(body(entries=[entry(prestate="owned", disposition="removed", content_sha256=None)])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("admits only ['installed', 'preserved', 'refreshed']", reasons_text(result))

    def test_an_empty_inventory_is_honest_only_for_a_refusal_that_moved_nothing(self) -> None:
        clean = seal(document(body(entries=[], effect_state="none", terminal_phase="not-activated")))
        self.assertEqual(clean["verdict"], SEALED, clean["reasons"])
        result = seal(document(body(entries=[])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("empty inventory is honest only", reasons_text(result))

    def test_a_not_activated_receipt_moved_nothing(self) -> None:
        result = seal(document(body(effect_state="none", terminal_phase="not-activated")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("a refusal before effect moved nothing", reasons_text(result))
        control = seal(
            document(
                body(
                    effect_state="none",
                    terminal_phase="not-activated",
                    entries=[entry(prestate="owned", disposition="preserved"), FOREIGN_ENTRY],
                )
            )
        )
        self.assertEqual(control["verdict"], SEALED, control["reasons"])


class EffectAndJournal(SealsClean):
    def test_an_effect_state_and_a_terminal_phase_that_disagree_are_refused(self) -> None:
        control = seal(document(partial_body()))
        self.assertEqual(control["verdict"], SEALED, control["reasons"])
        result = seal(document(body(effect_state="partial")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("that state admits only", reasons_text(result))

    def test_an_uninstall_cannot_terminate_activated(self) -> None:
        result = seal(
            document(
                body(
                    operation="uninstall",
                    entries=[entry(prestate="owned", disposition="removed", content_sha256=None)],
                )
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("that operation admits only ['not-activated', 'retired', 'unknown']", reasons_text(result))

    def test_an_install_cannot_terminate_retired(self) -> None:
        result = seal(document(body(terminal_phase="retired")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("terminal_phase 'retired'", reasons_text(result))

    def test_an_admitted_effect_binds_a_journal_or_names_the_unknown(self) -> None:
        named = partial_body(
            journal_sha256=None,
            unknowns=[
                {
                    "detail": "the journal was rotated before the digest was taken",
                    "observation": "journal-digest",
                    "subject": "journal_sha256",
                }
            ],
        )
        self.assertEqual(seal(document(named))["verdict"], SEALED)
        result = validate(resealed(partial_body(journal_sha256=None)))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("without binding a journal digest", reasons_text(result))

    def test_an_admitted_effect_binds_a_plan_digest(self) -> None:
        result = validate(resealed(partial_body(plan_sha256=None)))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("without binding a plan digest", reasons_text(result))

    def test_a_refusal_that_moved_nothing_needs_no_journal(self) -> None:
        clean = seal(
            document(
                body(
                    effect_state="none",
                    terminal_phase="not-activated",
                    entries=[FOREIGN_ENTRY],
                    journal_sha256=None,
                    plan_sha256=None,
                    archive_sha256=None,
                )
            )
        )
        self.assertEqual(clean["verdict"], SEALED, clean["reasons"])
        self.assertEqual(clean["receipt"]["body"]["unknowns"], [])


class UnknownsAndCoverage(SealsClean):
    def test_effect_complete_is_refused_beside_a_named_unknown(self) -> None:
        control = seal(document(partial_body(archive_sha256=None, unknowns=[dict(ARCHIVE_UNKNOWN)])))
        self.assertEqual(control["verdict"], SEALED, control["reasons"])
        result = seal(document(body(archive_sha256=None, unknowns=[dict(ARCHIVE_UNKNOWN)])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("is partial or unknown, never complete", reasons_text(result))
        self.assertIn("an unmade observation is not a fact", reasons_text(result))

    def test_the_producer_names_an_entry_content_unknown_it_discovered(self) -> None:
        observation = partial_body(
            entries=[entry(prestate="owned", disposition="refreshed", content_sha256=None)],
            unknowns=[],
        )
        result = seal(document(observation))
        self.assertEqual(result["verdict"], SEALED, result["reasons"])
        recorded = result["receipt"]["body"]["unknowns"]
        self.assertEqual(
            [(row["observation"], row["subject"]) for row in recorded],
            [("entry-content", "skills/agentic-sdlc")],
        )
        # POSITIVE CONTROL: a digestable entry produces NO unknown, so the assertion above is about
        # the null and not about the producer always appending something.
        clean = seal(document(partial_body(entries=[entry(prestate="owned", disposition="refreshed")])))
        self.assertEqual(clean["receipt"]["body"]["unknowns"], [])

    def test_a_producer_derived_unknown_blocks_effect_complete(self) -> None:
        # The derived record must reach the ADMISSION check, not merely the document.
        observation = body(
            entries=[entry(prestate="owned", disposition="refreshed", content_sha256=None)],
            unknowns=[],
        )
        result = seal(document(observation))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("never complete", reasons_text(result))

    def test_the_producer_names_a_null_archive_digest(self) -> None:
        result = seal(document(partial_body(archive_sha256=None, unknowns=[])))
        self.assertEqual(result["verdict"], SEALED, result["reasons"])
        self.assertEqual(
            [(row["observation"], row["subject"]) for row in result["receipt"]["body"]["unknowns"]],
            [("archive-digest", "archive_sha256")],
        )

    def test_an_undeclared_null_archive_digest_is_refused_on_validate(self) -> None:
        control = validate(resealed(partial_body(archive_sha256=None, unknowns=[dict(ARCHIVE_UNKNOWN)])))
        self.assertEqual(control["verdict"], VALIDATED, control["reasons"])
        result = validate(resealed(partial_body(archive_sha256=None, unknowns=[])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("name no archive-digest for it", reasons_text(result))

    def test_an_undeclared_null_entry_content_is_refused_on_validate(self) -> None:
        result = validate(
            resealed(
                partial_body(
                    entries=[entry(prestate="owned", disposition="preserved", content_sha256=None)],
                    unknowns=[],
                )
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("name no entry-content for it", reasons_text(result))

    def test_an_unknown_naming_no_entry_in_the_inventory_is_refused(self) -> None:
        result = seal(
            document(
                partial_body(
                    unknowns=[
                        {
                            "detail": "unreadable",
                            "observation": "entry-content",
                            "subject": "skills/not-in-this-receipt",
                        }
                    ]
                )
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("not an entry_name in this inventory", reasons_text(result))

    def test_a_fact_and_an_unknown_about_one_observation_are_a_contradiction(self) -> None:
        result = seal(document(partial_body(unknowns=[dict(ARCHIVE_UNKNOWN)])))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("a contradiction", reasons_text(result))

    def test_a_repeated_unknown_is_refused(self) -> None:
        result = seal(
            document(
                partial_body(
                    archive_sha256=None,
                    unknowns=[dict(ARCHIVE_UNKNOWN), dict(ARCHIVE_UNKNOWN)],
                )
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("repeats the unknown", reasons_text(result))

    def test_an_unknown_without_a_detail_is_refused(self) -> None:
        result = seal(
            document(
                partial_body(archive_sha256=None, unknowns=[{**ARCHIVE_UNKNOWN, "detail": ""}])
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("without a detail", reasons_text(result))

    def test_an_unlisted_observation_is_refused(self) -> None:
        result = seal(
            document(
                partial_body(
                    archive_sha256=None,
                    unknowns=[{**ARCHIVE_UNKNOWN, "observation": "vibes"}],
                )
            )
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("closed vocabulary", reasons_text(result))


class ChannelHonesty(SealsClean):
    def test_a_public_channel_is_refused(self) -> None:
        self.assertEqual(seal(document(body(public_channel=None)))["verdict"], SEALED)
        result = seal(document(body(public_channel="https://example.invalid/releases/latest")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("ADR-0021", reasons_text(result))

    def test_the_string_none_is_a_channel_named_none(self) -> None:
        result = seal(document(body(public_channel="none")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("a channel named 'none'", reasons_text(result))

    def test_any_release_claim_but_none_is_refused(self) -> None:
        for claim in ("published", "available", "ga", "tagged"):
            with self.subTest(claim=claim):
                result = seal(document(body(release_claim=claim)))
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn("no published release for a receipt to claim", reasons_text(result))

    def test_the_rendered_summary_states_the_honest_negative(self) -> None:
        result = seal(document())
        self.assertIn(
            "public_channel null and release_claim none: this receipt states no published release exists",
            result["rendered"],
        )


class TypedAncestors(SealsClean):
    def test_exactly_one_derived_from_names_the_acquisition_receipt(self) -> None:
        self.assertEqual(seal(document())["verdict"], SEALED)  # positive control
        for ancestors, expected in (
            ([], "0 derived-from"),
            ([dict(ACQUISITION_REFERENCE), {**ACQUISITION_REFERENCE, "receipt_id": "acquisition-2"}], "2 derived-from"),
        ):
            with self.subTest(count=expected):
                result = seal(document(ancestors=ancestors))
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn(expected, reasons_text(result))

    def test_an_update_supersedes_exactly_one_receipt(self) -> None:
        update = body(operation="update", entries=[entry(prestate="owned", disposition="refreshed")])
        supersedes = {"expected_kind": RECEIPT_KIND, "receipt_id": "activation-0", "relation": "supersedes"}
        clean = seal(document(update, ancestors=[dict(ACQUISITION_REFERENCE), supersedes]))
        self.assertEqual(clean["verdict"], SEALED, clean["reasons"])
        result = seal(document(update))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("operation 'update' with 0 supersedes", reasons_text(result))

    def test_an_install_that_supersedes_a_receipt_is_refused(self) -> None:
        supersedes = {"expected_kind": RECEIPT_KIND, "receipt_id": "activation-0", "relation": "supersedes"}
        result = seal(document(ancestors=[dict(ACQUISITION_REFERENCE), supersedes]))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("only an update replaces an earlier receipt", reasons_text(result))

    def test_a_relation_outside_this_family_is_refused(self) -> None:
        for relation in ("contained-by", "retries", "remediates"):
            with self.subTest(relation=relation):
                extra = {"expected_kind": RECEIPT_KIND, "receipt_id": "wave-node-1", "relation": relation}
                result = seal(document(ancestors=[dict(ACQUISITION_REFERENCE), extra]))
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn("this family uses only", reasons_text(result))
        # POSITIVE CONTROL: the three relations this family DOES use are admitted.
        evidence = {"expected_kind": "probe-qualification", "receipt_id": "probe-1", "relation": "references-evidence"}
        clean = seal(document(ancestors=[dict(ACQUISITION_REFERENCE), evidence]))
        self.assertEqual(clean["verdict"], SEALED, clean["reasons"])

    def test_a_derived_from_reference_expects_this_kind(self) -> None:
        result = seal(document(ancestors=[{**ACQUISITION_REFERENCE, "expected_kind": "probe-qualification"}]))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("the kind names the lifecycle family", reasons_text(result))

    def test_an_unlisted_relation_is_refused_as_a_closed_vocabulary(self) -> None:
        result = seal(document(ancestors=[{**ACQUISITION_REFERENCE, "relation": "caused-by"}]))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("closed vocabulary", reasons_text(result))

    def test_an_unknown_reference_field_is_refused(self) -> None:
        result = seal(document(ancestors=[{**ACQUISITION_REFERENCE, "why": "because"}]))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("the reference is closed", reasons_text(result))


class Trichotomy(SealsClean):
    """Absent, null, and empty are three facts, and each gets its own named reason."""

    def test_archive_digest_absent_null_and_empty_are_three_outcomes(self) -> None:
        absent = seal(document(body(archive_sha256=DROP)))
        null = seal(document(partial_body(archive_sha256=None)))
        empty = seal(document(body(archive_sha256="")))
        self.assertEqual(absent["verdict"], REFUSED)
        self.assertIn("carries no archive_sha256", reasons_text(absent))
        self.assertEqual(null["verdict"], SEALED, null["reasons"])
        self.assertEqual(empty["verdict"], REFUSED)
        self.assertIn("supplied and lost", reasons_text(empty))
        self.assertNotEqual(reasons_text(absent), reasons_text(empty))

    def test_requested_version_absent_null_and_empty_are_three_outcomes(self) -> None:
        absent = seal(document(body(requested_version=DROP)))
        null = seal(document(body(requested_version=None)))
        empty = seal(document(body(requested_version="")))
        self.assertEqual(absent["verdict"], REFUSED)
        self.assertIn("never spoke about the request", reasons_text(absent))
        self.assertEqual(null["verdict"], SEALED, null["reasons"])
        self.assertEqual(empty["verdict"], REFUSED)
        self.assertIn("a request supplied and lost", reasons_text(empty))

    def test_entry_content_absent_null_and_empty_are_three_outcomes(self) -> None:
        absent = seal(document(partial_body(entries=[entry(content_sha256=DROP)])))
        null = seal(document(partial_body(entries=[entry(prestate="owned", disposition="refreshed", content_sha256=None)])))
        empty = seal(document(partial_body(entries=[entry(content_sha256="")])))
        self.assertEqual(absent["verdict"], REFUSED)
        self.assertIn("carries no content_sha256", reasons_text(absent))
        self.assertEqual(null["verdict"], SEALED, null["reasons"])  # named as an unknown, not a hole
        self.assertEqual(empty["verdict"], REFUSED)
        self.assertIn("a digest supplied and lost", reasons_text(empty))

    def test_an_unsealed_body_records_the_placeholder_and_not_an_absence(self) -> None:
        absent = seal(document(body(record_sha256=DROP)))
        self.assertEqual(absent["verdict"], REFUSED)
        self.assertIn("carries no record_sha256", reasons_text(absent))
        # POSITIVE CONTROL: the explicit placeholder is what seal admits.
        self.assertEqual(seal(document(body(record_sha256="")))["verdict"], SEALED)

    def test_an_absent_unknowns_list_is_not_an_empty_one(self) -> None:
        result = seal(document(body(unknowns=DROP)))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("carries no unknowns", reasons_text(result))
        self.assertEqual(seal(document(body(unknowns=[])))["verdict"], SEALED)

    def test_the_field_reader_separates_absent_from_null(self) -> None:
        self.assertIs(dar.field({}, "key"), dar.ABSENT)
        self.assertIsNone(dar.field({"key": None}, "key"))
        # POSITIVE CONTROL: `.get` cannot tell these two apart, which is why `field` exists.
        self.assertEqual({}.get("key"), {"key": None}.get("key"))


HOSTILE_DETAIL = "digest failed\r\nrm -rf /\x1b[2Jgone\x7f"


class Rendering(SealsClean):
    def test_control_characters_are_escaped_in_every_rendered_line(self) -> None:
        observation = partial_body(
            archive_sha256=None,
            unknowns=[{**ARCHIVE_UNKNOWN, "detail": HOSTILE_DETAIL}],
        )
        result = seal(document(observation))
        self.assertEqual(result["verdict"], SEALED, result["reasons"])
        rendered = "\n".join(result["rendered"])
        self.assertNotIn("\r", rendered)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("\x7f", rendered)
        self.assertIn("\\r\\n", rendered)
        self.assertIn("\\x1b[2J", rendered)
        self.assertIn("\\x7f", rendered)
        # The line count is fixed, so an escaped newline cannot have forged an extra line.
        self.assertEqual(len(result["rendered"]), len(seal(document(partial_body(archive_sha256=None)))["rendered"]))

    def test_the_stored_detail_keeps_what_was_observed(self) -> None:
        receipt = sealed(
            document(
                partial_body(archive_sha256=None, unknowns=[{**ARCHIVE_UNKNOWN, "detail": HOSTILE_DETAIL}])
            )
        )
        self.assertEqual(receipt["body"]["unknowns"][0]["detail"], HOSTILE_DETAIL)

    def test_a_plain_detail_renders_verbatim(self) -> None:
        plain = "the archive was streamed and never landed as a file"
        result = seal(document(partial_body(archive_sha256=None, unknowns=[{**ARCHIVE_UNKNOWN, "detail": plain}])))
        self.assertIn(f"detail={plain}", "\n".join(result["rendered"]))

    def test_the_escape_helper_covers_the_whole_control_range(self) -> None:
        self.assertEqual(dar.escape_display("\x00\x1f\x7f"), "\\x00\\x1f\\x7f")
        self.assertEqual(dar.escape_display("\\"), "\\\\")
        self.assertEqual(dar.escape_display("plain"), "plain")
        # POSITIVE CONTROL: a naive `< 0x20` test would have let DEL through.
        self.assertLess(0x20, 0x7F)


class UnusableInput(unittest.TestCase):
    def test_an_overflowing_exponent_is_refused_as_unusable_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hostile = os.path.join(directory, "hostile.json")
            with open(hostile, "w", encoding="utf-8") as handle:
                handle.write('{"body": {"resolved_version": 1e400}}')
            proc = run_module("seal", "--observation", hostile)
            self.assertEqual(proc.returncode, EXIT_INPUT, proc.stdout)
            self.assertIn("non-finite", proc.stderr)
            # POSITIVE CONTROL: the same document with a FINITE float is a refusal, not exit 2, so
            # the code above came from the overflow and not from the surrounding shape.
            finite = os.path.join(directory, "finite.json")
            with open(finite, "w", encoding="utf-8") as handle:
                handle.write('{"body": {"resolved_version": 1.5}}')
            control = run_module("seal", "--observation", finite)
            self.assertEqual(control.returncode, EXIT_OK, control.stderr)
            self.assertEqual(json.loads(control.stdout)["verdict"], REFUSED)

    def test_a_non_finite_json_constant_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hostile = os.path.join(directory, "nan.json")
            with open(hostile, "w", encoding="utf-8") as handle:
                handle.write('{"body": {"resolved_version": NaN}}')
            proc = run_module("seal", "--observation", hostile)
            self.assertEqual(proc.returncode, EXIT_INPUT)
            self.assertIn("NaN", proc.stderr)

    def test_a_repeated_json_key_has_two_meanings_and_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hostile = os.path.join(directory, "twice.json")
            with open(hostile, "w", encoding="utf-8") as handle:
                handle.write('{"receipt_id": "a", "receipt_id": "b"}')
            proc = run_module("seal", "--observation", hostile)
            self.assertEqual(proc.returncode, EXIT_INPUT)
            self.assertIn("repeats the JSON key", proc.stderr)
            control = write_json(directory, "once.json", {"receipt_id": "a"})
            self.assertEqual(run_module("seal", "--observation", control).returncode, EXIT_OK)

    def test_a_directory_and_a_missing_path_are_unusable_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(run_module("seal", "--observation", directory).returncode, EXIT_INPUT)
            missing = os.path.join(directory, "nope.json")
            self.assertEqual(run_module("seal", "--observation", missing).returncode, EXIT_INPUT)
            control = write_json(directory, "ok.json", document())
            self.assertEqual(run_module("seal", "--observation", control).returncode, EXIT_OK)

    def test_a_json_array_is_not_a_receipt_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_json(directory, "list.json", [document()])
            proc = run_module("validate", "--receipt", path)
            self.assertEqual(proc.returncode, EXIT_INPUT)
            self.assertIn("not a JSON object", proc.stderr)


class SourceHygiene(unittest.TestCase):
    def _patterns(self) -> list[str]:
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        found: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if isinstance(target, ast.Attribute) and target.attr == "compile":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    found.append(node.args[0].value)
        return found

    def test_no_regex_uses_a_unicode_aware_character_class(self) -> None:
        patterns = self._patterns()
        self.assertGreaterEqual(len(patterns), 5)  # positive control: the walk found the regexes
        self.assertTrue(any("[0-9]" in pattern for pattern in patterns))
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertNotIn("\\d", pattern)
                self.assertNotIn("\\w", pattern)

    def test_every_closed_vocabulary_is_sorted_and_duplicate_free(self) -> None:
        for name in (
            "BODY_KEYS",
            "DISPOSITIONS",
            "EFFECT_STATES",
            "ENTRY_KEYS",
            "ENVELOPE_KEYS",
            "OBSERVATIONS",
            "OPERATIONS",
            "PRESTATES",
            "RECEIPT_KINDS",
            "REFERENCE_KEYS",
            "RELATIONS",
            "TERMINAL_PHASES",
            "UNKNOWN_KEYS",
            "VERSION_SOURCES",
        ):
            with self.subTest(name=name):
                value = getattr(dar, name)
                self.assertEqual(tuple(sorted(set(value))), tuple(value))

    def test_the_module_declares_the_effect_free_exit_space(self) -> None:
        self.assertEqual((dar.EXIT_OK, dar.EXIT_INTERNAL, dar.EXIT_INPUT), (0, 1, 2))
        for absent in ("EXIT_REFUSED", "EXIT_PARTIAL"):
            self.assertFalse(hasattr(dar, absent))

    def test_every_check_group_is_reachable_and_named(self) -> None:
        result = seal(document())
        self.assertEqual(tuple(result["checks"]), dar.CHECKS)
        self.assertEqual(result["reasons"], [])
        # POSITIVE CONTROL: each group can carry a reason, so the empty mapping above means clean.
        for slug, doc in (
            ("closed-key-set", document(note="x")),
            ("payload-identity", document(body(version_source="request"))),
            ("host-and-scope", document(body(host="all"))),
            ("entry-inventory", document(body(entries=[entry(), entry()]))),
            ("effect-and-journal", document(body(terminal_phase="retired"))),
            ("channel-honesty", document(body(release_claim="published"))),
            ("unknown-consistency", document(partial_body(unknowns=[dict(ARCHIVE_UNKNOWN)]))),
            ("typed-ancestors", document(ancestors=[])),
            ("record-seal", document(body(record_sha256=hexof("premature")))),
        ):
            with self.subTest(slug=slug):
                self.assertTrue(seal(doc)["checks"][slug], slug)


def acquisition_document(receipt_id: str = "acquisition-1") -> dict[str, Any]:
    """The ancestor, in envelope form. Its body is the ACQUISITION receipt's own shape.

    The envelope treats a body as opaque, so this fixture proves the correlation works across two
    DIFFERENT payload schemas of the same kind -- which is what "the kind names the lifecycle family"
    has to mean in practice.
    """
    payload = {
        "activation": "absent",
        "archive_sha256": hexof("archive"),
        "effect_state": "complete",
        "operation_id": "acquisition-of-0-6-3",
        "public_channel": None,
        "release_claim": "none",
        "schema_version": "release-candidate-acquisition-receipt/v1",
        "selection": "absent",
        "terminal_phase": "installed-unselected",
    }
    return {
        "ancestors": [],
        "body": payload,
        "content_digest": dar.envelope_content_digest(payload, "the acquisition receipt"),
        "emitting_plane": "release-candidate-acquisition",
        "receipt_id": receipt_id,
        "receipt_kind": RECEIPT_KIND,
        "schema": ENVELOPE_SCHEMA,
        "stated_at": "2026-08-19T09:00:00Z",
    }


def check_graph(*receipts: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "receipts.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            for receipt in receipts:
                handle.write(json.dumps(receipt) + "\n")
        proc = run_envelope("check-graph", "--receipts", path)
        if proc.returncode != EXIT_OK:
            raise AssertionError(f"the envelope checker exited {proc.returncode}: {proc.stderr}")
        return json.loads(proc.stdout)


class GraphInterop(unittest.TestCase):
    """The skills-plane checker owns the graph; this producer only has to write references it can resolve."""

    def test_the_acquisition_and_activation_pair_resolves_clean(self) -> None:
        report = check_graph(acquisition_document(), sealed())
        self.assertEqual(report["verdict"], "graph-clean", report)
        self.assertEqual(report["findings"], [])
        self.assertTrue(report["resolution_checked"])

    def test_a_derived_from_reference_to_a_missing_receipt_is_dangling(self) -> None:
        orphan = sealed(document(ancestors=[{**ACQUISITION_REFERENCE, "receipt_id": "acquisition-missing"}]))
        report = check_graph(acquisition_document(), orphan)
        self.assertEqual(report["verdict"], "graph-defective")
        self.assertEqual([row["finding"] for row in report["findings"]], ["dangling"])

    def test_a_repeated_reference_is_a_graph_finding_and_not_a_shape_refusal(self) -> None:
        evidence = {"expected_kind": "probe-qualification", "receipt_id": "probe-1", "relation": "references-evidence"}
        doc = document(ancestors=[dict(ACQUISITION_REFERENCE), dict(evidence), dict(evidence)])
        result = seal(doc)
        self.assertEqual(result["verdict"], SEALED, result["reasons"])  # shape: admitted here
        report = check_graph(acquisition_document(), result["receipt"])
        self.assertIn("duplicate", [row["finding"] for row in report["findings"]])

    def test_a_self_naming_reference_is_a_cyclic_finding_and_not_a_shape_refusal(self) -> None:
        itself = {"expected_kind": RECEIPT_KIND, "receipt_id": "activation-1", "relation": "references-evidence"}
        result = seal(document(ancestors=[dict(ACQUISITION_REFERENCE), itself]))
        self.assertEqual(result["verdict"], SEALED, result["reasons"])
        report = check_graph(acquisition_document(), result["receipt"])
        self.assertIn("cyclic", [row["finding"] for row in report["findings"]])

    def test_an_update_chain_supersedes_its_predecessor_and_still_resolves(self) -> None:
        first = sealed()
        update = body(operation="update", entries=[entry(prestate="owned", disposition="refreshed")])
        second = sealed(
            document(
                update,
                receipt_id="activation-2",
                ancestors=[
                    dict(ACQUISITION_REFERENCE),
                    {"expected_kind": RECEIPT_KIND, "receipt_id": "activation-1", "relation": "supersedes"},
                ],
            )
        )
        report = check_graph(acquisition_document(), first, second)
        self.assertEqual(report["verdict"], "graph-clean", report)


class CommandLine(unittest.TestCase):
    def test_help_prepares_nothing_and_exits_zero(self) -> None:
        for args in (("--help",), ("seal", "--help"), ("validate", "--help")):
            with self.subTest(args=args):
                proc = run_module(*args)
                self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
                # argparse re-wraps the epilog, so the assertion is on a phrase that cannot wrap.
                self.assertIn("Exit codes: 0 a result was derived", proc.stdout)

    def test_a_missing_subcommand_is_a_usage_error(self) -> None:
        self.assertEqual(run_module().returncode, EXIT_INPUT)

    def test_stdout_receives_exactly_the_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_json(directory, "observation.json", document())
            proc = subprocess.run(
                [sys.executable, str(MODULE), "seal", "--observation", path],
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
            self.assertTrue(proc.stdout.endswith(b"\n"))
            self.assertEqual(proc.stdout.count(b"\n"), 1)
            self.assertEqual(proc.stdout, dar.canonical_bytes(json.loads(proc.stdout.decode("ascii"))))

    def test_a_closed_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        if not os.path.exists("/bin/sh"):
            # Closing fd 2 before exec needs a POSIX shell to do it: this is the same named-skip
            # shape as the `/dev/full` control below, and windows-2025 reported it as a bare
            # `[WinError 2]` out of CreateProcess instead (agentic-sdlc-5ce7).
            self.skipTest("/bin/sh is unavailable, so stderr cannot be closed before exec")
        with tempfile.TemporaryDirectory() as directory:
            missing = os.path.join(directory, "nope.json")
            proc = subprocess.run(
                ["/bin/sh", "-c", f'exec 2>&-; "$1" "$2" seal --observation "$3"', "sh", sys.executable, str(MODULE), missing],
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, EXIT_INPUT)
            # POSITIVE CONTROL: with a stderr present the same run reports the reason.
            control = run_module("seal", "--observation", missing)
            self.assertEqual(control.returncode, EXIT_INPUT)
            self.assertIn("cannot read", control.stderr)

    def test_an_undeliverable_result_is_classified_and_not_inherited(self) -> None:
        if not os.path.exists("/dev/full"):
            self.skipTest("/dev/full is unavailable, so an unwritable stdout cannot be simulated")
        with tempfile.TemporaryDirectory() as directory:
            path = write_json(directory, "observation.json", document())
            with open("/dev/full", "w", encoding="utf-8") as sink:
                proc = subprocess.run(
                    [sys.executable, str(MODULE), "seal", "--observation", path],
                    stdout=sink,
                    stderr=subprocess.PIPE,
                    check=False,
                )
            self.assertEqual(proc.returncode, EXIT_INTERNAL)
            self.assertIn("derived but not delivered", proc.stderr.decode("utf-8"))
            # POSITIVE CONTROL: 120 is what an unclassified shutdown flush would have produced.
            self.assertNotEqual(proc.returncode, 120)


if __name__ == "__main__":
    unittest.main()
