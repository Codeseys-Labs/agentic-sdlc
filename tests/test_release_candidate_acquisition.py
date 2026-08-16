"""Closed contract tests for developer-only candidate acquisition."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_bundle.py"
POLICY_PATH = ROOT / "policy" / "release-candidate-acquisition.v1.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("bundle_validator_release_candidate_acquisition", VALIDATOR_PATH)


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def shipped_policy() -> dict[str, object]:
    value = json.loads(POLICY_PATH.read_text(encoding="ascii"))
    assert isinstance(value, dict)
    return value


def validate_raw(raw: bytes, *, neutralize_digest: bool = False) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy_dir = root / "policy"
        policy_dir.mkdir()
        (policy_dir / POLICY_PATH.name).write_bytes(raw)
        result = validator.Validation()
        expected_digest = hashlib.sha256(raw).hexdigest()
        digest = (
            mock.patch.object(
                validator,
                "RELEASE_CANDIDATE_ACQUISITION_POLICY_SHA256",
                expected_digest,
            )
            if neutralize_digest
            else mock.patch.object(
                validator,
                "RELEASE_CANDIDATE_ACQUISITION_POLICY_SHA256",
                validator.RELEASE_CANDIDATE_ACQUISITION_POLICY_SHA256,
            )
        )
        with digest:
            validator.validate_release_candidate_acquisition_policy(root, result)
        return result.errors


def validate_changed(change) -> list[str]:
    policy = copy.deepcopy(shipped_policy())
    change(policy)
    return validate_raw(canonical(policy), neutralize_digest=True)


def seal_record(record: dict[str, object]) -> dict[str, object]:
    value = copy.deepcopy(record)
    value.pop("record_sha256", None)
    record["record_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return record


def record_bytes(record: dict[str, object]) -> bytes:
    seal_record(record)
    return canonical(record)


def valid_operation_journal(
    phases: tuple[str, ...] = ("opened", "pinned", "staged"),
) -> dict[str, object]:
    effects = [
        "xdg-data-candidate-publish",
        "xdg-data-candidate-stage",
        "xdg-state-grant-consumption",
        "xdg-state-journal",
        "xdg-state-receipt",
        "xdg-state-writer-lock",
    ]
    timestamps = (
        "2026-08-16T12:00:00Z",
        "2026-08-16T12:00:01Z",
        "2026-08-16T12:00:02Z",
        "2026-08-16T12:00:03Z",
        "2026-08-16T12:00:04Z",
        "2026-08-16T12:00:05Z",
    )
    entries: list[dict[str, object]] = []
    for sequence, phase in enumerate(phases):
        predecessor = (
            None
            if sequence == 0
            else hashlib.sha256(canonical(entries[-1])).hexdigest()
        )
        entry = {
            "allowed_effects": list(effects),
            "archive_absolute_path": "/opt/candidates/candidate.tar.gz",
            "archive_sha256": "a" * 64,
            "archive_size_bytes": 4096,
            "candidate_root_sha256": "3" * 64,
            "effect_state": (
                "complete"
                if phase == "installed-unselected"
                else "partial"
            ),
            "effects_sha256": "b" * 64,
            "interpreter_relative_path": "runtime/python/bin/python3.12",
            "interpreter_sha256": "4" * 64,
            "operation_id": "op-0123456789abcdef0123456789abcdef",
            "phase": phase,
            "plan_sha256": "e" * 64,
            "previous_entry_sha256": predecessor,
            "record_sha256": "",
            "recorded_at": timestamps[sequence],
            "schema_version": "release-candidate-acquisition-journal-entry/v1",
            "sequence": sequence,
        }
        entries.append(seal_record(entry))
    return {
        "allowed_effects": list(effects),
        "archive_absolute_path": "/opt/candidates/candidate.tar.gz",
        "archive_sha256": "a" * 64,
        "archive_size_bytes": 4096,
        "effects_sha256": "b" * 64,
        "entries": entries,
        "operation_id": "op-0123456789abcdef0123456789abcdef",
        "plan_sha256": "e" * 64,
        "record_sha256": "",
        "schema_version": "release-candidate-acquisition-operation-journal/v1",
    }


def valid_recover_finish_grant() -> dict[str, object]:
    return {
        "archive_absolute_path": "/opt/candidates/candidate.tar.gz",
        "archive_sha256": "a" * 64,
        "archive_size_bytes": 4096,
        "decision": "finish",
        "effects_sha256": "b" * 64,
        "expires_at": "2026-08-16T12:10:00Z",
        "issued_at": "2026-08-16T12:00:00Z",
        "journal_absolute_physical_path": "/state/agentic-sdlc/acquisition/journals/op.json",
        "journal_sha256": "c" * 64,
        "nonce": "d" * 64,
        "operation_id": "op-0123456789abcdef0123456789abcdef",
        "original_effects": [
            "xdg-data-candidate-publish",
            "xdg-data-candidate-stage",
            "xdg-state-grant-consumption",
            "xdg-state-journal",
            "xdg-state-receipt",
            "xdg-state-writer-lock",
        ],
        "plan_sha256": "e" * 64,
        "record_sha256": "",
        "same_user_uid": 1000,
        "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
        "trust_root_absolute_path": "/opt/trust/candidate-root.json",
        "trust_root_sha256": "f" * 64,
        "xdg_data_home_absolute_path": "/home/operator/.local/share",
        "xdg_data_prestate_sha256": "1" * 64,
        "xdg_state_home_absolute_path": "/home/operator/.local/state",
        "xdg_state_prestate_sha256": "2" * 64,
    }


def valid_records() -> dict[str, dict[str, object]]:
    effects = [
        "xdg-data-candidate-publish",
        "xdg-data-candidate-stage",
        "xdg-state-grant-consumption",
        "xdg-state-journal",
        "xdg-state-receipt",
        "xdg-state-writer-lock",
    ]
    operation_id = "op-0123456789abcdef0123456789abcdef"
    plan = {
        "archive_absolute_path": "/opt/candidates/candidate.tar.gz",
        "archive_sha256": "a" * 64,
        "archive_size_bytes": 4096,
        "created_at": "2026-08-16T11:55:00Z",
        "effects_sha256": "b" * 64,
        "planned_effects": effects,
        "record_sha256": "",
        "schema_version": "release-candidate-acquisition-plan/v1",
        "trust_root_absolute_path": "/opt/trust/candidate-root.json",
        "trust_root_sha256": "f" * 64,
        "xdg_data_home_absolute_path": "/home/operator/.local/share",
        "xdg_data_prestate_sha256": "1" * 64,
        "xdg_state_home_absolute_path": "/home/operator/.local/state",
        "xdg_state_prestate_sha256": "2" * 64,
    }
    apply_grant = valid_recover_finish_grant()
    apply_grant.pop("journal_absolute_physical_path")
    apply_grant.pop("journal_sha256")
    apply_grant["decision"] = "apply"
    apply_grant["schema_version"] = "release-candidate-acquisition-apply-grant/v1"
    journal = {
        "allowed_effects": effects,
        "archive_absolute_path": "/opt/candidates/candidate.tar.gz",
        "archive_sha256": "a" * 64,
        "archive_size_bytes": 4096,
        "candidate_root_sha256": "3" * 64,
        "effect_state": "partial",
        "effects_sha256": "b" * 64,
        "interpreter_relative_path": "runtime/python/bin/python3.12",
        "interpreter_sha256": "4" * 64,
        "operation_id": operation_id,
        "phase": "staged",
        "plan_sha256": "e" * 64,
        "previous_entry_sha256": None,
        "record_sha256": "",
        "recorded_at": "2026-08-16T12:02:00Z",
        "schema_version": "release-candidate-acquisition-journal-entry/v1",
        "sequence": 0,
    }
    receipt = {
        "activation": "absent",
        "archive_sha256": "a" * 64,
        "candidate_root_absolute_physical_path": "/data/agentic-sdlc/acquisition/candidates/a/root",
        "effect_state": "complete",
        "installed_at": "2026-08-16T12:08:00Z",
        "journal_sha256": "c" * 64,
        "operation_id": operation_id,
        "plan_sha256": "e" * 64,
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "schema_version": "release-candidate-acquisition-receipt/v1",
        "selection": "absent",
        "support": "unsupported",
        "terminal_phase": "installed-unselected",
    }
    assessment = {
        "assessment_kind": "recover-inspect",
        "classification": "exact",
        "effect_state": "partial",
        "journal_locator": f"journal:{operation_id}",
        "last_proven_phase": "staged",
        "next_action": [
            "acquire", "recover", "inspect", "--journal-locator", "<journal-locator>",
        ],
        "operation_id": operation_id,
        "record_sha256": "",
        "schema_version": "release-candidate-acquisition-assessment/v1",
    }
    diagnostic = {
        "classification": "exact",
        "effect_state": "partial",
        "journal_locator": f"journal:{operation_id}",
        "last_proven_phase": "staged",
        "next_action": [
            "acquire", "recover", "inspect", "--journal-locator", "<journal-locator>",
        ],
        "operation_id": operation_id,
        "record_sha256": "",
        "schema_version": "release-candidate-acquisition-exit4-diagnostic/v1",
    }
    return {
        "acquisition_plan": plan,
        "apply_grant": apply_grant,
        "recover_finish_grant": valid_recover_finish_grant(),
        "journal_entry": journal,
        "operation_journal": valid_operation_journal(),
        "immutable_receipt": receipt,
        "assessment": assessment,
        "exit4_diagnostic": diagnostic,
    }


class AcquisitionPolicyIdentityTests(unittest.TestCase):
    def test_shipped_policy_is_exactly_admitted_and_canonical(self) -> None:
        result = validator.Validation()
        validator.validate_release_candidate_acquisition_policy(ROOT, result)
        self.assertEqual(result.errors, [], result.errors)
        policy = shipped_policy()
        self.assertEqual(POLICY_PATH.read_bytes(), canonical(policy))
        self.assertEqual(
            policy["canonical_json"],
            {
                "allow_nonfinite": False,
                "ensure_ascii": True,
                "separators": [",", ":"],
                "sort_keys": True,
                "trailing_newline": True,
            },
        )

    def test_strict_json_refuses_malformed_duplicate_nonfinite_and_noncanonical(self) -> None:
        cases = {
            "malformed": (b'{"schema_version":\n', "invalid strict JSON"),
            "duplicate": (
                b'{"schema_version":"a","schema_version":"b"}\n',
                "duplicate key 'schema_version'",
            ),
            "nan": (b'{"schema_version":NaN}\n', "non-finite JSON constant 'NaN'"),
            "infinity": (
                b'{"schema_version":Infinity}\n',
                "non-finite JSON constant 'Infinity'",
            ),
            "noncanonical": (
                b'{ "schema_version": "release-candidate-acquisition-policy/v1" }\n',
                "must use canonical ASCII compact JSON",
            ),
        }
        for label, (raw, message) in cases.items():
            with self.subTest(label=label):
                errors = validate_raw(raw)
                self.assertTrue(any(message in error for error in errors), errors)

    def test_unknown_top_level_and_nested_fields_are_refused(self) -> None:
        for label, change, message in (
            (
                "top",
                lambda p: p.__setitem__("extension", {}),
                "closed top-level schema mismatch",
            ),
            (
                "nested",
                lambda p: p["grant"].__setitem__("extension", True),
                "closed grant contract mismatch",
            ),
        ):
            with self.subTest(label=label):
                errors = validate_changed(change)
                self.assertTrue(any(message in error for error in errors), errors)
                self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_dispatcher_and_authoritative_gate_reach_this_policy(self) -> None:
        sentinel = RuntimeError("acquisition-policy-dispatch-sentinel")
        with mock.patch.object(
            validator,
            "validate_release_candidate_acquisition_policy",
            side_effect=sentinel,
        ) as called:
            with self.assertRaisesRegex(RuntimeError, "acquisition-policy-dispatch-sentinel"):
                validator.validate(ROOT)
        called.assert_called_once()

        mise = (ROOT / "mise.toml").read_text(encoding="utf-8")
        self.assertIn(
            'run = "uv run --python 3.12.11 --script scripts/validate_bundle.py"',
            mise,
        )
        self.assertIn('depends = ["validate", "test", "self-test", "secrets"]', mise)


class AcquisitionCommandAndStateTests(unittest.TestCase):
    def test_exit_codes_distinguish_internal_failure_from_clean_refusal(self) -> None:
        self.assertEqual(
            shipped_policy()["exit_codes"],
            {
                "0": "success-query-or-exact-no-effect",
                "1": "unexpected-internal-failure-before-admitted-effect",
                "2": "grammar-schema-or-invalid-input",
                "3": "clean-refusal-before-journal-or-product-effect",
                "4": "admitted-partial-or-unknown-effect",
            },
        )

        def swap_one_and_three(policy: dict[str, object]) -> None:
            exits = policy["exit_codes"]
            assert isinstance(exits, dict)
            exits["1"], exits["3"] = exits["3"], exits["1"]

        errors = validate_changed(swap_one_and_three)
        self.assertTrue(
            any("closed exit_codes contract mismatch" in error for error in errors),
            errors,
        )
        self.assertFalse(
            any("exact acquisition policy digest mismatch" in error for error in errors),
            errors,
        )

    def test_command_grammar_is_closed_and_read_only_commands_have_no_grant(self) -> None:
        commands = shipped_policy()["commands"]
        self.assertEqual(
            commands,
            [
                {
                    "argv": [
                        "acquire", "plan", "--archive", "<absolute-archive>",
                        "--trust-root", "<absolute-trust-root>",
                        "--xdg-data-home", "<absolute-xdg-data-home>",
                        "--xdg-state-home", "<absolute-xdg-state-home>",
                    ],
                    "effects": "none",
                    "grant": "forbidden",
                    "name": "plan",
                    "read_only": True,
                },
                {
                    "argv": ["acquire", "inspect", "--plan", "<absolute-plan>"],
                    "effects": "none",
                    "grant": "forbidden",
                    "name": "inspect",
                    "read_only": True,
                },
                {
                    "argv": [
                        "acquire", "apply", "--plan", "<absolute-plan>",
                        "--grant", "<absolute-grant>",
                    ],
                    "effects": "candidate-install",
                    "grant": "required",
                    "name": "apply",
                    "read_only": False,
                },
                {
                    "argv": [
                        "acquire", "recover", "inspect", "--journal-locator",
                        "<journal-locator>",
                    ],
                    "effects": "none",
                    "grant": "forbidden",
                    "name": "recover-inspect",
                    "read_only": True,
                },
                {
                    "argv": [
                        "acquire", "recover", "finish", "--journal-locator",
                        "<journal-locator>",
                        "--grant", "<absolute-grant>",
                    ],
                    "effects": "finish-candidate-install",
                    "grant": "required",
                    "name": "recover-finish",
                    "read_only": False,
                },
            ],
        )

    def test_phase_exit_and_effect_drift_are_refused(self) -> None:
        mutations = (
            ("state_machine", lambda p: p["state_machine"]["phases"].reverse()),
            ("state_machine", lambda p: p["state_machine"]["transitions"].pop()),
            ("exit_codes", lambda p: p["exit_codes"].__setitem__("4", "ordinary-failure")),
            ("exit_codes", lambda p: p["exit_codes"].__setitem__("5", "unknown")),
            ("commands", lambda p: p["commands"][0].__setitem__("effects", "candidate-install")),
            ("effects", lambda p: p["effects"].__setitem__("journal_before_candidate_data", False)),
            ("effects", lambda p: p["effects"]["no_replace_publication"].remove("receipt")),
            ("effects", lambda p: p["effects"]["serialized_writers"].append("plan")),
        )
        for section, change in mutations:
            with self.subTest(section=section):
                errors = validate_changed(change)
                self.assertTrue(
                    any(f"closed {section} contract mismatch" in error for error in errors),
                    errors,
                )
                self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_state_machine_ends_installed_but_unselected_and_reruns_have_no_effect(self) -> None:
        state = shipped_policy()["state_machine"]
        self.assertEqual(
            state["phases"],
            [
                "absent", "opened", "pinned", "staged", "published", "receipted",
                "installed-unselected",
            ],
        )
        self.assertEqual(state["terminal"], "installed-unselected")
        self.assertEqual(state["exact_rerun"], "success-no-effect")
        self.assertEqual(state["mismatched_rerun"], "safe-refusal-preserve")


class AcquisitionOperationJournalTests(unittest.TestCase):
    phases = (
        "opened",
        "pinned",
        "staged",
        "published",
        "receipted",
        "installed-unselected",
    )

    @staticmethod
    def _validate(
        journal: dict[str, object],
        *,
        policy: dict[str, object] | None = None,
        raw: bytes | None = None,
    ) -> list[str]:
        return validator.validate_release_candidate_acquisition_record(
            "operation_journal",
            raw if raw is not None else record_bytes(journal),
            policy or shipped_policy(),
        )

    @staticmethod
    def _changed(change) -> dict[str, object]:
        journal = valid_operation_journal()
        change(journal)
        entries = journal.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    seal_record(entry)
        return journal

    def test_every_nonempty_legal_prefix_is_a_valid_pending_or_complete_journal(self) -> None:
        for length in range(1, len(self.phases) + 1):
            journal = valid_operation_journal(self.phases[:length])
            with self.subTest(length=length):
                self.assertEqual(self._validate(journal), [])

    def test_policy_closes_complete_operation_journal_rules(self) -> None:
        self.assertEqual(
            shipped_policy()["records"]["journal_rules"],
            {
                "aggregate_limit": "limits.max_journal_bytes",
                "entry_bytes": "canonical-json-with-trailing-newline",
                "genesis": {
                    "phase": "opened",
                    "previous_entry_sha256": None,
                    "sequence": 0,
                },
                "identity_fields": [
                    "operation_id",
                    "archive_absolute_path",
                    "archive_sha256",
                    "archive_size_bytes",
                    "plan_sha256",
                    "effects_sha256",
                    "allowed_effects",
                ],
                "pending_prefixes_allowed": True,
                "phase_prefix": list(self.phases),
                "predecessor_digest": "sha256-of-exact-canonical-preceding-entry-bytes",
                "sequence": "zero-based-contiguous",
                "timestamp_order": "strict-utc-nondecreasing",
            },
        )

        errors = validate_changed(
            lambda p: p["records"]["journal_rules"]["genesis"].__setitem__(
                "previous_entry_sha256", "0" * 64
            )
        )
        self.assertTrue(any("closed records contract mismatch" in error for error in errors), errors)
        self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_journal_requires_exact_genesis_and_contiguous_digest_chain(self) -> None:
        cases = (
            (
                "empty",
                lambda j: j.__setitem__("entries", []),
                "operation journal requires genesis entry at sequence 0",
            ),
            (
                "missing-genesis",
                lambda j: j["entries"].pop(0),
                "operation journal requires genesis entry at sequence 0",
            ),
            (
                "sequence-three-zero-predecessor",
                lambda j: (
                    j["entries"][1].__setitem__("sequence", 3),
                    j["entries"][1].__setitem__("previous_entry_sha256", "0" * 64),
                ),
                "entry 1 sequence must equal 1",
            ),
            (
                "wrong-predecessor",
                lambda j: j["entries"][1].__setitem__(
                    "previous_entry_sha256", "9" * 64
                ),
                "entry 1 previous_entry_sha256 does not match exact preceding entry bytes",
            ),
        )
        for label, change, message in cases:
            with self.subTest(label=label):
                errors = self._validate(self._changed(change))
                self.assertTrue(any(message in error for error in errors), errors)

    def test_journal_rejects_skipped_reordered_duplicated_and_replaced_entries(self) -> None:
        def replace_with_other_operation(journal: dict[str, object]) -> None:
            replacement = copy.deepcopy(journal["entries"][1])
            replacement["operation_id"] = "op-fedcba9876543210fedcba9876543210"
            seal_record(replacement)
            journal["entries"][1] = replacement

        cases = (
            (
                "skipped",
                lambda j: j["entries"][1].__setitem__("phase", "staged"),
                "entry 1 phase must equal 'pinned'",
            ),
            (
                "reordered",
                lambda j: j["entries"].__setitem__(
                    slice(1, 3), [j["entries"][2], j["entries"][1]]
                ),
                "entry 1 phase must equal 'pinned'",
            ),
            (
                "duplicated",
                lambda j: j["entries"].insert(1, copy.deepcopy(j["entries"][0])),
                "entry 1 phase must equal 'pinned'",
            ),
            (
                "replaced",
                replace_with_other_operation,
                "entry 1 operation_id must equal journal operation_id",
            ),
        )
        for label, change, message in cases:
            with self.subTest(label=label):
                errors = self._validate(self._changed(change))
                self.assertTrue(any(message in error for error in errors), errors)

    def test_journal_identity_time_and_transition_are_immutable_across_entries(self) -> None:
        cases = (
            (
                "operation",
                lambda j: j["entries"][1].__setitem__(
                    "operation_id", "op-fedcba9876543210fedcba9876543210"
                ),
                "entry 1 operation_id must equal journal operation_id",
            ),
            (
                "archive",
                lambda j: j["entries"][1].__setitem__("archive_sha256", "5" * 64),
                "entry 1 archive identity must equal journal archive identity",
            ),
            (
                "plan",
                lambda j: j["entries"][1].__setitem__("plan_sha256", "6" * 64),
                "entry 1 plan_sha256 must equal journal plan_sha256",
            ),
            (
                "effects-digest",
                lambda j: j["entries"][1].__setitem__("effects_sha256", "7" * 64),
                "entry 1 effects_sha256 must equal journal effects_sha256",
            ),
            (
                "allowed-effects",
                lambda j: j["entries"][1]["allowed_effects"].pop(),
                "entry 1 allowed_effects must equal journal allowed_effects",
            ),
            (
                "nonmonotonic-time",
                lambda j: j["entries"][1].__setitem__(
                    "recorded_at", "2026-08-16T11:59:59Z"
                ),
                "entry 1 recorded_at is earlier than preceding entry",
            ),
            (
                "illegal-transition",
                lambda j: j["entries"][1].__setitem__("phase", "absent"),
                "entry 1 phase must equal 'pinned'",
            ),
        )
        for label, change, message in cases:
            with self.subTest(label=label):
                errors = self._validate(self._changed(change))
                self.assertTrue(any(message in error for error in errors), errors)

    def test_journal_record_is_closed_versioned_canonical_and_bounded(self) -> None:
        cases = (
            (
                "extra",
                lambda j: j.__setitem__("repair", True),
                "has extra keys: ['repair']",
            ),
            (
                "wrong-version",
                lambda j: j.__setitem__(
                    "schema_version", "release-candidate-acquisition-operation-journal/v2"
                ),
                "schema_version must equal 'release-candidate-acquisition-operation-journal/v1'",
            ),
        )
        for label, change, message in cases:
            journal = valid_operation_journal()
            change(journal)
            with self.subTest(label=label):
                errors = self._validate(journal)
                self.assertTrue(any(message in error for error in errors), errors)

        journal = valid_operation_journal()
        raw = record_bytes(journal)
        pretty = json.dumps(json.loads(raw), indent=2, sort_keys=True).encode("ascii") + b"\n"
        errors = self._validate(journal, raw=pretty)
        self.assertTrue(any("must use canonical ASCII compact JSON" in error for error in errors), errors)

        bounded_policy = copy.deepcopy(shipped_policy())
        bounded_policy["limits"]["max_journal_bytes"] = len(raw) - 1
        errors = self._validate(journal, policy=bounded_policy, raw=raw)
        self.assertTrue(any("operation_journal exceeds max_journal_bytes" in error for error in errors), errors)


class AcquisitionEffectTaxonomyTests(unittest.TestCase):
    preterminal = ("opened", "pinned", "staged", "published", "receipted")
    terminal = "installed-unselected"

    @staticmethod
    def _validate(kind: str, record: dict[str, object]) -> list[str]:
        return validator.validate_release_candidate_acquisition_record(
            kind,
            record_bytes(record),
            shipped_policy(),
        )

    def test_policy_closes_phase_effect_taxonomy_without_digest_help(self) -> None:
        self.assertEqual(
            shipped_policy()["records"]["effect_state_rules"],
            {
                "assessment": {
                    "exact_by_phase": {
                        "absent": "none",
                        "opened": "partial",
                        "pinned": "partial",
                        "staged": "partial",
                        "published": "partial",
                        "receipted": "partial",
                        "installed-unselected": "complete",
                    },
                    "unavailable": {
                        "effect_state": "unknown",
                        "forbidden_last_proven_phases": ["installed-unselected"],
                    },
                },
                "classification_vocabulary": ["exact", "unavailable"],
                "exit4": {
                    "allowed_effect_states": ["partial", "unknown"],
                    "partial": {
                        "classification": "exact",
                        "last_proven_phases": list(self.preterminal),
                    },
                    "unknown": {
                        "classification": "unavailable",
                        "forbidden_last_proven_phases": ["installed-unselected"],
                    },
                },
                "journal_effect_state_by_phase": {
                    "opened": "partial",
                    "pinned": "partial",
                    "staged": "partial",
                    "published": "partial",
                    "receipted": "partial",
                    "installed-unselected": "complete",
                },
                "none_scope": "pre-journal-absent-assessment-only",
                "unknown_scope": "assessment-or-exit4-with-unavailable-classification-only",
            },
        )
        errors = validate_changed(
            lambda p: p["records"]["effect_state_rules"][
                "journal_effect_state_by_phase"
            ].__setitem__("opened", "complete")
        )
        self.assertTrue(any("closed records contract mismatch" in error for error in errors), errors)
        self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_journal_phase_effect_cross_product_is_exact(self) -> None:
        mapping = {phase: "partial" for phase in self.preterminal}
        mapping[self.terminal] = "complete"
        all_states = ("none", "partial", "unknown", "complete")
        phases = (*self.preterminal, self.terminal)
        for index, phase in enumerate(phases):
            for effect_state in all_states:
                journal = valid_operation_journal(phases[: index + 1])
                entry = journal["entries"][-1]
                entry["effect_state"] = effect_state
                seal_record(entry)
                errors = validator.validate_release_candidate_acquisition_record(
                    "operation_journal",
                    record_bytes(journal),
                    shipped_policy(),
                )
                with self.subTest(phase=phase, effect_state=effect_state):
                    if effect_state == mapping[phase]:
                        self.assertEqual(errors, [], errors)
                    else:
                        message = (
                            f"journal_entry record effect_state must equal {mapping[phase]!r} "
                            f"for phase {phase!r}"
                        )
                        self.assertTrue(
                            any(
                                f"entry {index}:" in error and message in error
                                for error in errors
                            ),
                            errors,
                        )

    def test_standalone_journal_entry_phase_effect_cross_product_is_exact(self) -> None:
        mapping = {phase: "partial" for phase in self.preterminal}
        mapping[self.terminal] = "complete"
        all_states = ("none", "partial", "unknown", "complete")
        phases = (*self.preterminal, self.terminal)
        for index, phase in enumerate(phases):
            for effect_state in all_states:
                entry = valid_operation_journal(phases[: index + 1])["entries"][-1]
                entry["effect_state"] = effect_state
                errors = self._validate("journal_entry", entry)
                with self.subTest(phase=phase, effect_state=effect_state):
                    if effect_state == mapping[phase]:
                        self.assertEqual(errors, [], errors)
                    else:
                        message = (
                            f"journal_entry record effect_state must equal "
                            f"{mapping[phase]!r} for phase {phase!r}"
                        )
                        self.assertTrue(any(message in error for error in errors), errors)

    def test_standalone_journal_entry_direct_effect_regressions(self) -> None:
        cases = (
            ("opened", "complete", "partial"),
            (self.terminal, "partial", "complete"),
            (self.terminal, "unknown", "complete"),
        )
        phases = (*self.preterminal, self.terminal)
        for phase, effect_state, expected in cases:
            index = phases.index(phase)
            entry = valid_operation_journal(phases[: index + 1])["entries"][-1]
            entry["effect_state"] = effect_state
            with self.subTest(phase=phase, effect_state=effect_state):
                errors = self._validate("journal_entry", entry)
                message = (
                    f"journal_entry record effect_state must equal "
                    f"{expected!r} for phase {phase!r}"
                )
                self.assertTrue(any(message in error for error in errors), errors)

    def test_assessment_state_is_bound_to_exact_or_unavailable_classification(self) -> None:
        exact_mapping = {"absent": "none", **{phase: "partial" for phase in self.preterminal}}
        exact_mapping[self.terminal] = "complete"
        for phase, effect_state in exact_mapping.items():
            assessment = valid_records()["assessment"]
            assessment["classification"] = "exact"
            assessment["last_proven_phase"] = phase
            assessment["effect_state"] = effect_state
            with self.subTest(valid_exact=phase):
                self.assertEqual(self._validate("assessment", assessment), [])

        unavailable = valid_records()["assessment"]
        unavailable["classification"] = "unavailable"
        unavailable["last_proven_phase"] = "staged"
        unavailable["effect_state"] = "unknown"
        self.assertEqual(self._validate("assessment", unavailable), [])

        cases = (
            ("false-complete", "exact", "staged", "complete", "must equal 'partial'"),
            ("preterminal-none", "exact", "opened", "none", "must equal 'partial'"),
            ("preterminal-unknown", "exact", "receipted", "unknown", "must equal 'partial'"),
            ("terminal-partial", "exact", self.terminal, "partial", "must equal 'complete'"),
            (
                "terminal-unknown",
                "unavailable",
                self.terminal,
                "unknown",
                "unavailable classification cannot claim terminal phase",
            ),
        )
        for label, classification, phase, effect_state, message in cases:
            assessment = valid_records()["assessment"]
            assessment["classification"] = classification
            assessment["last_proven_phase"] = phase
            assessment["effect_state"] = effect_state
            with self.subTest(label=label):
                errors = self._validate("assessment", assessment)
                self.assertTrue(any(message in error for error in errors), errors)

    def test_exit4_state_phase_and_classification_are_compatible(self) -> None:
        valid_cases = (
            ("exact", "partial", "opened"),
            ("exact", "partial", "receipted"),
            ("unavailable", "unknown", "absent"),
            ("unavailable", "unknown", "staged"),
        )
        for classification, effect_state, phase in valid_cases:
            diagnostic = valid_records()["exit4_diagnostic"]
            diagnostic["classification"] = classification
            diagnostic["effect_state"] = effect_state
            diagnostic["last_proven_phase"] = phase
            with self.subTest(valid=(classification, effect_state, phase)):
                self.assertEqual(self._validate("exit4_diagnostic", diagnostic), [])

        cases = (
            (
                "partial-terminal",
                "exact",
                "partial",
                self.terminal,
                "partial requires an exact preterminal last_proven_phase",
            ),
            (
                "unknown-terminal",
                "unavailable",
                "unknown",
                self.terminal,
                "unknown classification cannot claim terminal phase",
            ),
            (
                "partial-unavailable",
                "unavailable",
                "partial",
                "staged",
                "partial requires classification 'exact'",
            ),
            (
                "unknown-exact",
                "exact",
                "unknown",
                "staged",
                "unknown requires classification 'unavailable'",
            ),
            ("complete", "exact", "complete", "staged", "must be partial or unknown"),
            ("none", "exact", "none", "absent", "must be partial or unknown"),
        )
        for label, classification, effect_state, phase, message in cases:
            diagnostic = valid_records()["exit4_diagnostic"]
            diagnostic["classification"] = classification
            diagnostic["effect_state"] = effect_state
            diagnostic["last_proven_phase"] = phase
            with self.subTest(label=label):
                errors = self._validate("exit4_diagnostic", diagnostic)
                self.assertTrue(any(message in error for error in errors), errors)


class AcquisitionAuthorityInvariantTests(unittest.TestCase):
    def _validate_record(
        self,
        kind: str,
        record: dict[str, object],
        *,
        now: str = "2026-08-16T12:05:00Z",
        consumed_nonces: set[str] | None = None,
        effective_uid: int = 1000,
        expected_authority: dict[str, object] | None = None,
    ) -> list[str]:
        return validator.validate_release_candidate_acquisition_record(
            kind,
            record_bytes(record),
            shipped_policy(),
            now_utc=now,
            consumed_nonces=consumed_nonces or set(),
            effective_uid=effective_uid,
            expected_authority=expected_authority,
        )

    @staticmethod
    def _grant_authority(record: dict[str, object]) -> dict[str, object]:
        keys = [
            "archive_absolute_path",
            "archive_sha256",
            "archive_size_bytes",
            "decision",
            "effects_sha256",
            "operation_id",
            "original_effects",
            "plan_sha256",
            "trust_root_absolute_path",
            "trust_root_sha256",
            "xdg_data_home_absolute_path",
            "xdg_data_prestate_sha256",
            "xdg_state_home_absolute_path",
            "xdg_state_prestate_sha256",
        ]
        if record.get("decision") == "finish":
            keys.extend(["journal_absolute_physical_path", "journal_sha256"])
        return {
            key: copy.deepcopy(record[key])
            for key in keys
        }

    def test_grant_records_enforce_utc_ttl_freshness_and_replay(self) -> None:
        grant = valid_recover_finish_grant()
        authority = self._grant_authority(grant)
        self.assertEqual(
            self._validate_record("recover_finish_grant", grant, expected_authority=authority),
            [],
        )

        cases = (
            (
                "malformed-issued-at",
                lambda r: r.__setitem__("issued_at", "2026-08-16 12:00:00Z"),
                "issued_at must use strict UTC",
                "2026-08-16T12:05:00Z",
                set(),
            ),
            (
                "expires-before-issued",
                lambda r: r.__setitem__("expires_at", "2026-08-16T11:59:59Z"),
                "expires_at must be after issued_at",
                "2026-08-16T12:05:00Z",
                set(),
            ),
            (
                "long-ttl",
                lambda r: r.__setitem__("expires_at", "2026-08-16T12:15:01Z"),
                "grant TTL exceeds 900 seconds",
                "2026-08-16T12:05:00Z",
                set(),
            ),
            (
                "stale",
                lambda r: None,
                "grant is expired",
                "2026-08-16T12:10:00Z",
                set(),
            ),
            (
                "replay",
                lambda r: None,
                "grant nonce was already consumed",
                "2026-08-16T12:05:00Z",
                {"d" * 64},
            ),
        )
        for label, change, message, now, consumed in cases:
            changed = valid_recover_finish_grant()
            change(changed)
            with self.subTest(label=label):
                errors = self._validate_record(
                    "recover_finish_grant",
                    changed,
                    now=now,
                    consumed_nonces=consumed,
                    expected_authority=authority,
                )
                self.assertTrue(any(message in error for error in errors), errors)

    def test_recover_finish_refuses_cross_operation_and_cross_journal_substitution(self) -> None:
        original = valid_recover_finish_grant()
        authority = self._grant_authority(original)
        cases = (
            (
                "operation",
                lambda r: r.__setitem__("operation_id", "op-fedcba9876543210fedcba9876543210"),
                "operation_id does not match expected authority",
            ),
            (
                "journal-path",
                lambda r: r.__setitem__(
                    "journal_absolute_physical_path",
                    "/state/agentic-sdlc/acquisition/journals/other.json",
                ),
                "journal_absolute_physical_path does not match expected authority",
            ),
            (
                "journal-digest",
                lambda r: r.__setitem__("journal_sha256", "3" * 64),
                "journal_sha256 does not match expected authority",
            ),
            (
                "decision",
                lambda r: r.__setitem__("decision", "apply"),
                "decision must equal 'finish'",
            ),
            (
                "original-effects",
                lambda r: r["original_effects"].pop(),
                "original_effects must equal",
            ),
        )
        for label, change, message in cases:
            changed = valid_recover_finish_grant()
            change(changed)
            with self.subTest(label=label):
                errors = self._validate_record(
                    "recover_finish_grant",
                    changed,
                    expected_authority=authority,
                )
                self.assertTrue(any(message in error for error in errors), errors)

    def test_recover_finish_grant_binds_exact_canonical_operation_journal_bytes(self) -> None:
        journal = valid_operation_journal()
        journal_raw = record_bytes(journal)
        grant = valid_recover_finish_grant()
        grant["operation_id"] = journal["operation_id"]
        grant["journal_sha256"] = hashlib.sha256(journal_raw).hexdigest()
        authority = self._grant_authority(grant)
        self.assertEqual(
            self._validate_record(
                "recover_finish_grant",
                grant,
                expected_authority=authority,
            ),
            [],
        )

        changed_journal = valid_operation_journal()
        changed_journal["entries"][1]["recorded_at"] = "2026-08-16T12:00:03Z"
        seal_record(changed_journal["entries"][1])
        changed_raw = record_bytes(changed_journal)
        changed_authority = copy.deepcopy(authority)
        changed_authority["journal_sha256"] = hashlib.sha256(changed_raw).hexdigest()
        errors = self._validate_record(
            "recover_finish_grant",
            grant,
            expected_authority=changed_authority,
        )
        self.assertTrue(
            any("journal_sha256 does not match expected authority" in error for error in errors),
            errors,
        )

    def test_all_versioned_record_families_admit_only_closed_canonical_records(self) -> None:
        for kind, record in valid_records().items():
            with self.subTest(kind=kind):
                errors = self._validate_record(
                    kind,
                    record,
                    expected_authority=(
                        self._grant_authority(record)
                        if kind in {"apply_grant", "recover_finish_grant"}
                        else None
                    ),
                )
                self.assertEqual(errors, [], errors)

    def test_record_contract_rejects_omitted_extra_wrong_version_and_malformed_fields(self) -> None:
        cases = (
            (
                "omitted",
                "acquisition_plan",
                lambda r: r.pop("archive_sha256"),
                "missing required keys: ['archive_sha256']",
            ),
            (
                "extra",
                "immutable_receipt",
                lambda r: r.__setitem__("promotion", "stable"),
                "has extra keys: ['promotion']",
            ),
            (
                "wrong-version",
                "journal_entry",
                lambda r: r.__setitem__("schema_version", "release-candidate-acquisition-journal-entry/v2"),
                "schema_version must equal 'release-candidate-acquisition-journal-entry/v1'",
            ),
            (
                "malformed-field",
                "acquisition_plan",
                lambda r: r.__setitem__("archive_sha256", "ABC"),
                "archive_sha256 must be a lowercase SHA-256",
            ),
        )
        records = valid_records()
        for label, kind, change, message in cases:
            changed = copy.deepcopy(records[kind])
            change(changed)
            with self.subTest(label=label):
                errors = self._validate_record(kind, changed)
                self.assertTrue(any(message in error for error in errors), errors)

    def test_archive_size_is_positive_integer_and_never_exceeds_policy_cap(self) -> None:
        cap = shipped_policy()["limits"]["max_archive_bytes"]
        records = valid_records()
        for kind in (
            "acquisition_plan",
            "apply_grant",
            "recover_finish_grant",
            "journal_entry",
            "operation_journal",
        ):
            for label, value, message in (
                ("over-cap", cap + 1, f"archive_size_bytes exceeds max_archive_bytes {cap}"),
                ("negative", -1, "archive_size_bytes must be a positive-integer"),
                ("bool", True, "archive_size_bytes must be a positive-integer"),
            ):
                changed = copy.deepcopy(records[kind])
                changed["archive_size_bytes"] = value
                authority = (
                    self._grant_authority(changed)
                    if kind in {"apply_grant", "recover_finish_grant"}
                    else None
                )
                with self.subTest(kind=kind, label=label):
                    errors = self._validate_record(
                        kind,
                        changed,
                        expected_authority=authority,
                    )
                    self.assertTrue(any(message in error for error in errors), errors)

    def test_grant_validation_requires_complete_runtime_context_and_same_user(self) -> None:
        grant = valid_recover_finish_grant()
        raw = record_bytes(grant)
        errors = validator.validate_release_candidate_acquisition_record(
            "recover_finish_grant",
            raw,
            shipped_policy(),
        )
        for message in (
            "grant validation requires now_utc",
            "grant validation requires consumed_nonces",
            "grant validation requires effective_uid",
            "grant validation requires the complete expected authority",
        ):
            self.assertTrue(any(message in error for error in errors), errors)

        errors = self._validate_record(
            "recover_finish_grant",
            grant,
            effective_uid=1001,
            expected_authority=self._grant_authority(grant),
        )
        self.assertTrue(any("same_user_uid does not match effective_uid" in error for error in errors), errors)

        noncanonical = valid_records()["acquisition_plan"]
        raw = record_bytes(noncanonical)
        pretty = json.dumps(json.loads(raw), indent=2, sort_keys=True).encode("ascii") + b"\n"
        errors = validator.validate_release_candidate_acquisition_record(
            "acquisition_plan", pretty, shipped_policy()
        )
        self.assertTrue(any("must use canonical ASCII compact JSON" in error for error in errors), errors)

        malformed_records = (
            (
                b'{"schema_version":"a","schema_version":"b"}\n',
                "duplicate key 'schema_version'",
            ),
            (b'{"schema_version":NaN}\n', "non-finite JSON constant 'NaN'"),
            (b'{"schema_version":\n', "invalid strict JSON"),
        )
        for raw, message in malformed_records:
            with self.subTest(message=message):
                errors = validator.validate_release_candidate_acquisition_record(
                    "acquisition_plan", raw, shipped_policy()
                )
                self.assertTrue(any(message in error for error in errors), errors)

    def test_exit_four_diagnostic_is_bounded_and_has_exactly_one_closed_next_action(self) -> None:
        valid = valid_records()["exit4_diagnostic"]
        self.assertEqual(self._validate_record("exit4_diagnostic", valid), [])
        cases = (
            (
                "missing-state",
                lambda r: r.pop("effect_state"),
                "missing required keys: ['effect_state']",
            ),
            (
                "unsupported-state",
                lambda r: r.__setitem__("effect_state", "complete"),
                "effect_state is outside the closed vocabulary",
            ),
            (
                "missing-locator",
                lambda r: r.pop("journal_locator"),
                "missing required keys: ['journal_locator']",
            ),
            (
                "unbounded-locator",
                lambda r: r.__setitem__("journal_locator", "journal:" + "x" * 300),
                "journal_locator must be an opaque ASCII locator of at most 256 bytes",
            ),
            (
                "missing-phase",
                lambda r: r.pop("last_proven_phase"),
                "missing required keys: ['last_proven_phase']",
            ),
            (
                "unsupported-action",
                lambda r: r.__setitem__("next_action", ["acquire", "rollback"]),
                "next_action is outside the closed vocabulary",
            ),
            (
                "multiple-actions",
                lambda r: r.__setitem__(
                    "next_action",
                    [
                        ["acquire", "recover", "inspect"],
                        ["acquire", "recover", "finish"],
                    ],
                ),
                "next_action is outside the closed vocabulary",
            ),
        )
        for label, change, message in cases:
            changed = copy.deepcopy(valid)
            change(changed)
            with self.subTest(label=label):
                errors = self._validate_record("exit4_diagnostic", changed)
                self.assertTrue(any(message in error for error in errors), errors)

    def test_private_python_recovery_is_acquired_root_only_and_journal_pinned(self) -> None:
        recovery = shipped_policy()["recovery"]
        self.assertEqual(
            recovery["private_python"],
            {
                "arguments": ["-I", "-B"],
                "execution_root": "acquired-root",
                "interpreter_journal_pins": [
                    "candidate_root_sha256",
                    "interpreter_relative_path",
                    "interpreter_sha256",
                ],
                "relative_path": "runtime/python/bin/python3.12",
                "requires_existing_journal_pin": True,
                "role": "acquired-root-continuity-evidence",
                "self_authentication": False,
                "source_checkout": "unavailable-and-not-required",
            },
        )
        cases = (
            lambda p: p["recovery"]["private_python"].__setitem__(
                "source_checkout", "required"
            ),
            lambda p: p["recovery"]["private_python"].__setitem__(
                "relative_path", "usr/bin/python3"
            ),
            lambda p: p["recovery"]["private_python"].__setitem__(
                "arguments", ["-B"]
            ),
        )
        for index, change in enumerate(cases):
            with self.subTest(index=index):
                errors = validate_changed(change)
                self.assertTrue(
                    any("closed recovery contract mismatch" in error for error in errors),
                    errors,
                )
                self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_section_validators_reject_semantic_drift_without_digest_help(self) -> None:
        cases = (
            (
                "effects",
                lambda p: p["effects"]["exit_routing"].__setitem__(
                    "internal_incomplete_after_journal", 1
                ),
            ),
            (
                "grant",
                lambda p: p["grant"]["runtime_checks"].remove("nonce-not-consumed"),
            ),
            (
                "records",
                lambda p: p["records"]["schemas"].pop("operation_journal"),
            ),
            (
                "records",
                lambda p: p["records"]["journal_binding"].__setitem__(
                    "journal_sha256", "unbound"
                ),
            ),
            (
                "recovery",
                lambda p: p["recovery"]["private_python"].__setitem__(
                    "self_authentication", True
                ),
            ),
        )
        for section, change in cases:
            with self.subTest(section=section):
                errors = validate_changed(change)
                self.assertTrue(
                    any(f"closed {section} contract mismatch" in error for error in errors),
                    errors,
                )
                self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_grants_are_external_procedural_single_use_same_user_and_exactly_bound(self) -> None:
        grant = shipped_policy()["grant"]
        self.assertFalse(grant["approval_authenticated"])
        self.assertFalse(grant["minted_by_tool"])
        self.assertTrue(grant["expiring"])
        self.assertTrue(grant["same_user"])
        self.assertTrue(grant["single_use"])
        self.assertEqual(grant["required_by"], ["apply", "recover-finish"])
        self.assertEqual(
            grant["bound_fields"],
            {
                "apply": [
                    "decision", "operation_id", "plan_sha256", "archive.absolute_path",
                    "archive.sha256", "archive.size_bytes", "trust_root.absolute_path",
                    "trust_root.sha256", "xdg_data_home.absolute_path",
                    "xdg_data_home.prestate_sha256", "xdg_state_home.absolute_path",
                    "xdg_state_home.prestate_sha256", "effects.sha256",
                    "original_allowed_effects", "same_user_uid", "issued_at", "expires_at",
                    "nonce",
                ],
                "recover-finish": [
                    "decision", "operation_id", "journal.absolute_physical_path",
                    "journal.sha256", "plan_sha256", "archive.absolute_path",
                    "archive.sha256", "archive.size_bytes", "trust_root.absolute_path",
                    "trust_root.sha256", "xdg_data_home.absolute_path",
                    "xdg_data_home.prestate_sha256", "xdg_state_home.absolute_path",
                    "xdg_state_home.prestate_sha256", "effects.sha256",
                    "original_allowed_effects", "same_user_uid", "issued_at", "expires_at",
                    "nonce",
                ],
            },
        )

    def test_grant_and_nonclaim_mutations_are_refused(self) -> None:
        mutations = (
            ("grant", lambda p: p["grant"].__setitem__("approval_authenticated", True)),
            ("grant", lambda p: p["grant"].__setitem__("minted_by_tool", True)),
            ("grant", lambda p: p["grant"].__setitem__("single_use", False)),
            (
                "grant",
                lambda p: p["grant"]["bound_fields"]["apply"].remove("effects.sha256"),
            ),
            ("commands", lambda p: p["commands"][1].__setitem__("grant", "required")),
            ("disclosures", lambda p: p["disclosures"].__setitem__("public_channel", "preview")),
            ("disclosures", lambda p: p["disclosures"].__setitem__("support", "experimental")),
            ("disclosures", lambda p: p["disclosures"].__setitem__("provenance", "verified")),
            ("disclosures", lambda p: p["disclosures"].__setitem__("selection", "present")),
        )
        for section, change in mutations:
            with self.subTest(section=section):
                errors = validate_changed(change)
                self.assertTrue(
                    any(f"closed {section} contract mismatch" in error for error in errors),
                    errors,
                )
                self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_platform_layout_limit_and_vocabulary_drift_are_refused(self) -> None:
        mutations = (
            ("platform", lambda p: p["platform"].__setitem__("architecture", "arm64")),
            ("platform", lambda p: p["platform"].__setitem__("other_platforms", "experimental")),
            ("filesystem", lambda p: p["filesystem"]["layout"].__setitem__("writer_lock", "elsewhere")),
            ("filesystem", lambda p: p["filesystem"].__setitem__("implicit_environment_defaults", True)),
            ("limits", lambda p: p["limits"].__setitem__("max_archive_bytes", 0)),
            ("limits", lambda p: p["limits"].__setitem__("max_archive_bytes", 536_870_913)),
            ("preservation", lambda p: p["preservation"]["preserved_states"].remove("foreign")),
            ("authority", lambda p: p["authority"]["forbidden_effects"].remove("network")),
            ("redaction", lambda p: p["redaction"]["forbidden_output"].remove("grant-body")),
        )
        for section, change in mutations:
            with self.subTest(section=section):
                errors = validate_changed(change)
                self.assertTrue(
                    any(f"closed {section} contract mismatch" in error for error in errors),
                    errors,
                )
                self.assertFalse(any("digest mismatch" in error for error in errors), errors)

    def test_recovery_can_only_finish_and_private_python_is_not_self_authentication(self) -> None:
        recovery = shipped_policy()["recovery"]
        self.assertTrue(recovery["finish_only"])
        self.assertFalse(recovery["rollback"])
        self.assertFalse(recovery["delete"])
        self.assertEqual(
            recovery["private_python"],
            {
                "arguments": ["-I", "-B"],
                "execution_root": "acquired-root",
                "interpreter_journal_pins": [
                    "candidate_root_sha256",
                    "interpreter_relative_path",
                    "interpreter_sha256",
                ],
                "relative_path": "runtime/python/bin/python3.12",
                "requires_existing_journal_pin": True,
                "role": "acquired-root-continuity-evidence",
                "self_authentication": False,
                "source_checkout": "unavailable-and-not-required",
            },
        )
        for change in (
            lambda p: p["recovery"].__setitem__("rollback", True),
            lambda p: p["recovery"].__setitem__("delete", True),
            lambda p: p["recovery"]["private_python"].__setitem__("self_authentication", True),
        ):
            errors = validate_changed(change)
            self.assertTrue(
                any("closed recovery contract mismatch" in error for error in errors),
                errors,
            )
            self.assertFalse(any("digest mismatch" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
