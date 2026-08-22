"""Closed contract tests for developer-only candidate acquisition."""
from __future__ import annotations

import contextlib
import copy
import errno
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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
CANDIDATE_PATH = ROOT / "scripts" / "release_candidate.py"


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
    timestamps: tuple[str, ...] | None = None,
) -> dict[str, object]:
    effects = [
        "xdg-data-candidate-publish",
        "xdg-data-candidate-stage",
        "xdg-state-grant-consumption",
        "xdg-state-journal",
        "xdg-state-receipt",
        "xdg-state-writer-lock",
    ]
    # Supplying `timestamps` rebuilds the hash chain around them, so a clock-shaped fixture carries
    # no collateral seal or predecessor error and a validation result can be asserted EXACTLY. Checked
    # with `is None` rather than `timestamps or (...)`: an explicitly supplied but EMPTY tuple is a
    # real, distinct fixture request (zero phases means zero timestamps too), and `or` would silently
    # replace it with the six-entry default instead of honoring the caller's empty tuple.
    if timestamps is None:
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
        "journal_locator": f"journal:v1:{operation_id}:{'c' * 64}",
        "last_proven_phase": "staged",
        "next_action": [
            "acquire", "recover", "inspect", "--xdg-state-home",
            "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>",
        ],
        "operation_id": operation_id,
        "record_sha256": "",
        "schema_version": "release-candidate-acquisition-assessment/v1",
    }
    diagnostic = {
        "classification": "exact",
        "effect_state": "partial",
        "journal_locator": f"journal:v1:{operation_id}:{'c' * 64}",
        "last_proven_phase": "staged",
        "next_action": [
            "acquire", "recover", "inspect", "--xdg-state-home",
            "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>",
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
                        "acquire", "recover", "inspect", "--xdg-state-home",
                        "<absolute-xdg-state-home>", "--journal-locator",
                        "<journal-locator>",
                    ],
                    "effects": "none",
                    "grant": "forbidden",
                    "name": "recover-inspect",
                    "read_only": True,
                },
                {
                    "argv": [
                        "acquire", "recover", "finish", "--xdg-state-home",
                        "<absolute-xdg-state-home>", "--journal-locator",
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
                # A literal, deliberately: the validator derives the same string from its tolerance
                # constant, so this is the third side of the triangle that makes a silent retune
                # impossible -- policy bytes, validator constant, and this expectation must agree.
                "timestamp_order": "utc-nondecreasing-within-2.0s-backward-clock-tolerance",
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
                # Four seconds below entry 0, i.e. past the bounded clock-step tolerance that
                # test_a_bounded_backwards_clock_step_is_tolerated_and_a_larger_one_is_not pins
                # from both sides. A one-second regression is deliberately NOT a defect here.
                "nonmonotonic-time",
                lambda j: j["entries"][1].__setitem__(
                    "recorded_at", "2026-08-16T11:59:56Z"
                ),
                "entry 1 recorded_at regresses more than 2.0s below the preceding entries",
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

    def test_a_bounded_backwards_clock_step_is_tolerated_and_a_larger_one_is_not(self) -> None:
        """agentic-sdlc-184b: `recorded_at` is CLOCK_REALTIME, and a real clock steps backwards.

        The measured steps on the WSL2 development host were 0.22-0.53s. Entries are recorded
        whole-second, so a sub-second step is invisible unless two appends straddle a second
        boundary; when they do, a 0.5s step is exactly the ONE-SECOND regression pinned below. Two
        seconds is the documented bound (also asserted directly, at the resolution the steps were
        measured at, in test_the_backwards_clock_tolerance_is_the_documented_measured_bound).
        """
        tolerated = {
            "same-second": ("2026-08-16T12:00:00Z",) * 3,
            "one-second-step": (
                "2026-08-16T12:00:01Z",
                "2026-08-16T12:00:00Z",
                "2026-08-16T12:00:02Z",
            ),
            "two-second-step-is-the-inclusive-bound": (
                "2026-08-16T12:00:03Z",
                "2026-08-16T12:00:01Z",
                "2026-08-16T12:00:04Z",
            ),
            "slide-totalling-the-bound": (
                "2026-08-16T12:00:02Z",
                "2026-08-16T12:00:01Z",
                "2026-08-16T12:00:00Z",
            ),
        }
        for label, timestamps in tolerated.items():
            with self.subTest(tolerated=label):
                journal = valid_operation_journal(self.phases[:3], timestamps)
                # Exactly no errors, not merely no ordering error: the fixture rebuilds the seal and
                # the predecessor chain around these timestamps, so anything here is a real defect.
                self.assertEqual(self._validate(journal), [])

        refused = {
            "three-second-step": (
                (
                    "2026-08-16T12:00:03Z",
                    "2026-08-16T12:00:00Z",
                    "2026-08-16T12:00:04Z",
                ),
                1,
            ),
            "slide-past-the-bound-one-tolerated-second-at-a-time": (
                (
                    "2026-08-16T12:00:03Z",
                    "2026-08-16T12:00:02Z",
                    "2026-08-16T12:00:01Z",
                    "2026-08-16T12:00:00Z",
                ),
                3,
            ),
        }
        for label, (timestamps, index) in refused.items():
            with self.subTest(refused=label):
                journal = valid_operation_journal(self.phases[: len(timestamps)], timestamps)
                self.assertEqual(
                    self._validate(journal),
                    [
                        "release-candidate acquisition operation_journal record "
                        f"entry {index} recorded_at regresses more than 2.0s "
                        "below the preceding entries"
                    ],
                )

    def test_the_backwards_clock_tolerance_is_the_documented_measured_bound(self) -> None:
        # The whole-second record format cannot express the measured 0.22-0.53s steps, so the
        # tolerance is pinned here at the resolution it was measured at, in both directions.
        self.assertEqual(validator.ACQUISITION_RECORDED_AT_BACKWARD_TOLERANCE_SECONDS, 2.0)
        prior = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
        for seconds in (0.0, 0.22, 0.53, 0.5, 1.0, 2.0):
            with self.subTest(tolerated_seconds=seconds):
                self.assertFalse(
                    validator._acquisition_recorded_at_regresses(
                        prior, prior - timedelta(seconds=seconds)
                    )
                )
        for seconds in (2.001, 3.0, 60.0):
            with self.subTest(refused_seconds=seconds):
                self.assertTrue(
                    validator._acquisition_recorded_at_regresses(
                        prior, prior - timedelta(seconds=seconds)
                    )
                )
        # Forwards is never a regression, whatever the gap.
        self.assertFalse(
            validator._acquisition_recorded_at_regresses(prior, prior + timedelta(hours=1))
        )

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
                "journal_locator must be a non-disclosing journal:v1 operation and digest handle",
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


class AcquisitionEngineGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = load_module("release_candidate_engine_under_test", CANDIDATE_PATH)

    def test_dispatcher_accepts_only_the_frozen_acquisition_grammar(self) -> None:
        accepted = (
            ["acquire", "plan", "--archive", "/a.tar.gz", "--trust-root", "/trust", "--xdg-data-home", "/data", "--xdg-state-home", "/state"],
            ["acquire", "inspect", "--plan", "/plan.json"],
            ["acquire", "apply", "--plan", "/plan.json", "--grant", "/grant.json"],
            ["acquire", "recover", "inspect", "--xdg-state-home", "/state", "--journal-locator", f"journal:v1:op-0123456789abcdef0123456789abcdef:{'c' * 64}"],
            ["acquire", "recover", "finish", "--xdg-state-home", "/state", "--journal-locator", f"journal:v1:op-0123456789abcdef0123456789abcdef:{'c' * 64}", "--grant", "/grant.json"],
        )
        for argv in accepted:
            with self.subTest(argv=argv):
                self.assertEqual(self.candidate.parse_args(argv).action, "acquire")

        refused = (
            ["acquire", "plan", "--archive", "/a.tar.gz"],
            ["acquire", "inspect"],
            ["acquire", "apply", "--archive", "/a.tar.gz", "--plan", "/plan.json", "--grant", "/grant.json"],
            ["acquire", "recover", "inspect"],
            ["acquire", "recover", "inspect", "--journal-locator", f"journal:v1:op-0123456789abcdef0123456789abcdef:{'c' * 64}"],
            ["acquire", "recover", "finish", "--grant", "/grant.json"],
            ["acquire", "recover", "finish", "--journal-locator", f"journal:v1:op-0123456789abcdef0123456789abcdef:{'c' * 64}", "--grant", "/grant.json"],
            ["acquire", "rollback"],
        )
        for argv in refused:
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                self.candidate.parse_args(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_plan_and_inspect_are_canonical_and_write_nothing_under_explicit_roots(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            data, state = case / "data", case / "state"
            data.mkdir(mode=0o700)
            state.mkdir(mode=0o700)
            archive = case / f"agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz"
            archive.write_bytes(b"not-structurally-admitted-during-plan\n")
            archive.chmod(0o600)
            trust = ROOT / "policy" / "release-candidate.v1.json"
            poison = {
                **os.environ,
                "HOME": str(case / "poison-home"),
                "XDG_DATA_HOME": str(case / "poison-data"),
                "XDG_STATE_HOME": str(case / "poison-state"),
                "TMPDIR": str(case / "poison-tmp"),
                "HTTPS_PROXY": "http://credential-canary.invalid/path",
                "ANTHROPIC_API_KEY": "credential-canary",
            }
            before = sorted(path.relative_to(case).as_posix() for path in case.rglob("*"))
            planned = subprocess.run(
                [
                    sys.executable, str(CANDIDATE_PATH), "acquire", "plan",
                    "--archive", str(archive), "--trust-root", str(trust),
                    "--xdg-data-home", str(data), "--xdg-state-home", str(state),
                ],
                cwd=ROOT, env=poison, capture_output=True, check=False,
            )
            self.assertEqual(planned.returncode, 0, planned.stderr.decode())
            self.assertEqual(planned.stderr, b"")
            plan = json.loads(planned.stdout)
            self.assertEqual(planned.stdout, canonical(plan))
            self.assertEqual(plan["xdg_data_home_absolute_path"], str(data))
            self.assertEqual(plan["xdg_state_home_absolute_path"], str(state))
            after_plan = sorted(path.relative_to(case).as_posix() for path in case.rglob("*"))
            self.assertEqual(after_plan, before)
            self.assertFalse((case / "poison-data").exists())
            self.assertFalse((case / "poison-state").exists())
            self.assertNotIn(b"credential-canary", planned.stdout + planned.stderr)

            plan_path = case / "plan.json"
            plan_path.write_bytes(planned.stdout)
            plan_path.chmod(0o600)
            before_inspect = sorted(path.relative_to(case).as_posix() for path in case.rglob("*"))
            inspected = subprocess.run(
                [sys.executable, str(CANDIDATE_PATH), "acquire", "inspect", "--plan", str(plan_path)],
                cwd=ROOT, env=poison, capture_output=True, check=False,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr.decode())
            assessment = json.loads(inspected.stdout)
            self.assertEqual(inspected.stdout, canonical(assessment))
            self.assertEqual(assessment["effect_state"], "none")
            self.assertEqual(assessment["last_proven_phase"], "absent")
            after_inspect = sorted(path.relative_to(case).as_posix() for path in case.rglob("*"))
            self.assertEqual(after_inspect, before_inspect)
            self.assertFalse((case / "poison-data").exists())
            self.assertFalse((case / "poison-state").exists())


class _StopAfterStagedCopy(Exception):
    """Ends the real `_stage_candidate` at its first step after the archive copy.

    It is raised from inside the engine's own `_open_dir_at`, so the copy runs exactly as
    production runs it — including where production sources the admitted digest — and the
    inflation, admission and extraction that need a genuine candidate archive never start.
    """


class AcquisitionEngineLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = load_module("release_candidate_lifecycle_under_test", CANDIDATE_PATH)
        cls.engine = load_module(
            "release_candidate_acquisition_lifecycle_under_test",
            ROOT / "scripts" / "release_candidate_acquisition.py",
        )
        cls.policy, cls.validator, cls.source_root = cls.engine._load_policy(cls.candidate)

    def _records(self, case: Path) -> tuple[SimpleNamespace, str, str]:
        data, state = case / "data", case / "state"
        data.mkdir(mode=0o700); state.mkdir(mode=0o700)
        archive = case / f"agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz"
        archive.write_bytes(b"archive-evidence\n"); archive.chmod(0o600)
        trust = ROOT / "policy" / "release-candidate.v1.json"
        data_pin = self.engine._root_pin(data, "data")
        state_pin = self.engine._root_pin(state, "state")
        try:
            plan = {
                "archive_absolute_path": str(archive),
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "archive_size_bytes": archive.stat().st_size,
                "created_at": self.engine._timestamp(),
                "effects_sha256": self.engine._effects_sha(),
                "planned_effects": list(self.engine.EFFECTS),
                "record_sha256": "",
                "schema_version": "release-candidate-acquisition-plan/v1",
                "trust_root_absolute_path": str(trust),
                "trust_root_sha256": hashlib.sha256(trust.read_bytes()).hexdigest(),
                "xdg_data_home_absolute_path": str(data),
                "xdg_data_prestate_sha256": data_pin.prestate_sha256,
                "xdg_state_home_absolute_path": str(state),
                "xdg_state_prestate_sha256": state_pin.prestate_sha256,
            }
        finally:
            data_pin.close(); state_pin.close()
        plan_raw = record_bytes(plan)
        plan_path = case / "plan.json"; plan_path.write_bytes(plan_raw); plan_path.chmod(0o600)
        plan_sha = hashlib.sha256(plan_raw).hexdigest()
        operation = "op-0123456789abcdef0123456789abcdef"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        grant = {
            "archive_absolute_path": plan["archive_absolute_path"],
            "archive_sha256": plan["archive_sha256"],
            "archive_size_bytes": plan["archive_size_bytes"],
            "decision": "apply",
            "effects_sha256": plan["effects_sha256"],
            "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "nonce": "b" * 64,
            "operation_id": operation,
            "original_effects": list(self.engine.EFFECTS),
            "plan_sha256": plan_sha,
            "record_sha256": "",
            "same_user_uid": os.geteuid(),
            "schema_version": "release-candidate-acquisition-apply-grant/v1",
            "trust_root_absolute_path": plan["trust_root_absolute_path"],
            "trust_root_sha256": plan["trust_root_sha256"],
            "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"],
            "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
            "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"],
            "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
        }
        grant_path = case / "grant.json"; grant_path.write_bytes(record_bytes(grant)); grant_path.chmod(0o600)
        return SimpleNamespace(plan=plan_path, grant=grant_path), operation, str(plan["archive_sha256"])

    def _fake_stage(self, stage, archive_fd: int, archive_item, plan, candidate, source_root):
        del candidate, source_root
        stage_path = self.engine._fd_path(stage.fd)
        archive = stage_path / "candidate.tar.gz"
        with archive.open("wb") as handle:
            os.lseek(archive_fd, 0, os.SEEK_SET)
            handle.write(os.read(archive_fd, archive_item.st_size))
        archive.chmod(0o600)
        interpreter = stage_path / "root" / "runtime" / "python" / "bin" / "python3.12"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_bytes(b"private-python\n"); interpreter.chmod(0o755)
        scripts = stage_path / "root" / "scripts"
        scripts.mkdir()
        (scripts / "release_candidate.py").write_bytes(b"dispatcher\n")
        (scripts / "release_candidate_acquisition.py").write_bytes(b"acquisition\n")
        manifest = stage_path / "root" / "manifest.json"
        manifest.write_bytes(
            canonical(
                {
                    "candidate_id": "a" * 64,
                    "inventory": [
                        {
                            "path": "scripts/release_candidate.py",
                            "sha256": hashlib.sha256(b"dispatcher\n").hexdigest(),
                        },
                        {
                            "path": "scripts/release_candidate_acquisition.py",
                            "sha256": hashlib.sha256(b"acquisition\n").hexdigest(),
                        },
                    ],
                }
            )
        )
        manifest.chmod(0o644)
        root_pin, _created = self.engine._open_dir_at(
            stage.fd,
            "root",
            stage.display_path,
            create=False,
            partial=True,
            allowed_modes=(0o755,),
        )
        try:
            root_sha = self.engine._tree_sha_fd(root_pin, partial=True)
        finally:
            root_pin.close()
        return root_sha, hashlib.sha256(interpreter.read_bytes()).hexdigest()

    @staticmethod
    def _snapshot(root: Path) -> dict[str, tuple[int, int, int, bytes | None]]:
        return {
            path.relative_to(root).as_posix(): (
                path.lstat().st_ino,
                path.lstat().st_mtime_ns,
                stat.S_IMODE(path.lstat().st_mode),
                path.read_bytes() if path.is_file() else None,
            )
            for path in root.rglob("*")
        }

    def _staged_recovery_case(
        self,
        case: Path,
        *,
        nonce: str,
    ) -> tuple[SimpleNamespace, str, str, str, Path]:
        arguments, operation, archive_sha = self._records(case)
        output = io.BytesIO()
        errors = io.BytesIO()
        stdout = SimpleNamespace(
            buffer=output,
            write=lambda text: output.write(text.encode("utf-8")),
        )
        stderr = SimpleNamespace(
            buffer=errors,
            write=lambda text: errors.write(text.encode("utf-8")),
        )

        def fault(phase: str) -> None:
            if phase == "staged":
                raise RuntimeError("staged boundary")

        trust = ROOT / "policy" / "release-candidate.v1.json"
        with (
            mock.patch.object(
                self.engine,
                "_trust_root",
                return_value=(trust, hashlib.sha256(trust.read_bytes()).hexdigest()),
            ),
            mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
            mock.patch.object(self.engine, "_TEST_FAULT_HOOK", fault),
            mock.patch.object(self.engine.sys, "stdout", stdout),
            mock.patch.object(self.engine.sys, "stderr", stderr),
        ):
            self.assertEqual(
                self.engine.apply_hardened(
                    arguments,
                    self.candidate,
                    self.policy,
                    self.validator,
                    self.source_root,
                ),
                4,
            )

        locator = json.loads(errors.getvalue())["journal_locator"]
        journal_path = (
            case
            / "state"
            / "agentic-sdlc"
            / "acquisition"
            / "journals"
            / f"{operation}.json"
        )
        plan_raw = arguments.plan.read_bytes()
        plan = json.loads(plan_raw)
        journal_raw = journal_path.read_bytes()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        grant = {
            "archive_absolute_path": plan["archive_absolute_path"],
            "archive_sha256": plan["archive_sha256"],
            "archive_size_bytes": plan["archive_size_bytes"],
            "decision": "finish",
            "effects_sha256": plan["effects_sha256"],
            "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "journal_absolute_physical_path": str(journal_path),
            "journal_sha256": hashlib.sha256(journal_raw).hexdigest(),
            "nonce": nonce,
            "operation_id": operation,
            "original_effects": list(self.engine.EFFECTS),
            "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
            "record_sha256": "",
            "same_user_uid": os.geteuid(),
            "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
            "trust_root_absolute_path": plan["trust_root_absolute_path"],
            "trust_root_sha256": plan["trust_root_sha256"],
            "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"],
            "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
            "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"],
            "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
        }
        recovery_grant = case / "recovery-timeout-grant.json"
        recovery_grant.write_bytes(record_bytes(grant))
        recovery_grant.chmod(0o600)
        return (
            SimpleNamespace(
                acquire_action="recover",
                recover_action="finish",
                xdg_state_home=case / "state",
                journal_locator=locator,
                grant=recovery_grant,
            ),
            operation,
            archive_sha,
            locator,
            journal_path,
        )

    def test_external_plan_and_grant_records_are_bounded_descriptor_pins(self) -> None:
        def run_inspect(case: Path, plan: Path, hook=None) -> int:
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            with (
                mock.patch.object(self.engine, "_TEST_EXTERNAL_RACE_HOOK", hook),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                return self.engine.run(
                    SimpleNamespace(acquire_action="inspect", plan=plan),
                    candidate=self.candidate,
                )

        # Type, symlink, safe-mode, and pre-allocation size checks all fail closed.
        for label, prepare in {
            "symlink": lambda path, original: path.symlink_to(original),
            "unsafe-mode": lambda path, _original: path.chmod(0o644),
            "directory": lambda path, _original: (path.unlink(), path.mkdir(mode=0o700)),
            "oversized-sparse": lambda path, _original: os.truncate(
                path, int(self.policy["limits"]["max_plan_bytes"]) + 1
            ),
        }.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
                original = case / "original-plan.json"
                if label == "symlink":
                    arguments.plan.rename(original)
                prepare(arguments.plan, original)
                before = self._snapshot(case)
                self.assertEqual(run_inspect(case, arguments.plan), 2)
                self.assertEqual(self._snapshot(case), before)
                self.assertFalse((case / "state" / "agentic-sdlc").exists())
                self.assertFalse((case / "data" / "agentic-sdlc").exists())

        # Namespace replacement after open, same-inode mutation after read, and
        # short-read after the pre-allocation fstat are all detected through the
        # public inspect seam.
        for label in ("replacement", "same-inode-mutation", "short-read"):
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
                original_raw = arguments.plan.read_bytes()
                fired = False
                def race(point: str, path: Path, fd: int) -> None:
                    nonlocal fired
                    if fired or not point.endswith(":plan-input"):
                        return
                    expected = {
                        "replacement": "external-after-open:plan-input",
                        "same-inode-mutation": "external-after-read:plan-input",
                        "short-read": "external-after-stat:plan-input",
                    }[label]
                    if point != expected:
                        return
                    fired = True
                    if label == "replacement":
                        path.rename(path.with_name("held-plan.json"))
                        path.write_bytes(original_raw); path.chmod(0o600)
                    elif label == "same-inode-mutation":
                        with path.open("ab") as handle:
                            handle.write(b" ")
                    else:
                        os.ftruncate(fd, max(1, len(original_raw) // 2))
                self.assertEqual(run_inspect(case, arguments.plan, race), 2)
                self.assertTrue(fired)
                self.assertFalse((case / "state" / "agentic-sdlc").exists())
                self.assertFalse((case / "data" / "agentic-sdlc").exists())

        # Grant replacement is caught before the first target effect.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
            original_raw = arguments.grant.read_bytes(); fired = False
            def grant_race(point: str, path: Path, _fd: int) -> None:
                nonlocal fired
                if point == "external-after-open:grant-input" and not fired:
                    fired = True
                    path.rename(path.with_name("held-grant.json"))
                    path.write_bytes(original_raw); path.chmod(0o600)
            before = self._snapshot(case)
            with (
                mock.patch.object(self.engine, "_TEST_EXTERNAL_RACE_HOOK", grant_race),
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
            ):
                with self.assertRaises(self.engine.AcquisitionFailure) as raised:
                    self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root)
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertTrue(fired)
            # The test-owned external input changed, but explicit target roots did not.
            after = self._snapshot(case)
            for relative, evidence in before.items():
                if relative not in {"grant.json"}:
                    self.assertEqual(after.get(relative), evidence)
            self.assertFalse((case / "state" / "agentic-sdlc").exists())
            self.assertFalse((case / "data" / "agentic-sdlc").exists())

        for label in ("symlink", "unsafe-mode", "oversized-sparse", "short-read", "growth"):
            with self.subTest(grant=label), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
                original_raw = arguments.grant.read_bytes(); fired = False
                if label == "symlink":
                    held = arguments.grant.with_name("held-grant.json")
                    arguments.grant.rename(held); arguments.grant.symlink_to(held)
                elif label == "unsafe-mode":
                    arguments.grant.chmod(0o644)
                elif label == "oversized-sparse":
                    os.truncate(arguments.grant, int(self.policy["limits"]["max_grant_bytes"]) + 1)
                def grant_fault(point: str, path: Path, fd: int) -> None:
                    nonlocal fired
                    expected = {
                        "short-read": "external-after-stat:grant-input",
                        "growth": "external-after-stat:grant-input",
                    }.get(label)
                    if fired or point != expected:
                        return
                    fired = True
                    if label == "short-read":
                        os.ftruncate(fd, max(1, len(original_raw) // 2))
                    else:
                        with path.open("ab") as handle:
                            handle.write(b" ")
                with (
                    mock.patch.object(self.engine, "_TEST_EXTERNAL_RACE_HOOK", grant_fault),
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                ):
                    result = self.engine.run(
                        SimpleNamespace(acquire_action="apply", plan=arguments.plan, grant=arguments.grant),
                        candidate=self.candidate,
                    )
                self.assertEqual(result, 2)
                if label in {"short-read", "growth"}:
                    self.assertTrue(fired)
                self.assertFalse((case / "state" / "agentic-sdlc").exists())
                self.assertFalse((case / "data" / "agentic-sdlc").exists())

    def test_grant_bound_opened_bootstrap_is_the_first_durable_namespace_effect(self) -> None:
        expectations = {
            "first-before-create": (3, False, False),
            "first-after-create": (4, True, False),
            "first-after-write": (4, True, True),
            "first-after-file-fsync": (4, True, True),
            "first-after-parent-fsync": (4, True, True),
        }
        for point, (expected_exit, exists, exact) in expectations.items():
            with self.subTest(point=point), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, operation, _archive_sha = self._records(case)
                output = io.BytesIO(); errors = io.BytesIO(); seen: list[str] = []
                stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
                stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
                def fault(actual: str) -> None:
                    seen.append(actual)
                    if actual == point:
                        raise RuntimeError("first-effect crash")
                with (
                    mock.patch.object(self.engine, "_TEST_FIRST_EFFECT_HOOK", fault),
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                    mock.patch.object(self.engine.sys, "stdout", stdout),
                    mock.patch.object(self.engine.sys, "stderr", stderr),
                ):
                    result = self.engine.run(
                        SimpleNamespace(acquire_action="apply", plan=arguments.plan, grant=arguments.grant),
                        candidate=self.candidate,
                    )
                self.assertEqual(result, expected_exit)
                self.assertIn(point, seen)
                bootstrap = list((case / "state").glob(".agentic-sdlc-acquisition-v1-*.opened.json"))
                self.assertEqual(bool(bootstrap), exists)
                self.assertFalse((case / "state" / "agentic-sdlc").exists())
                self.assertFalse((case / "data" / "agentic-sdlc").exists())
                self.assertEqual(list(case.rglob("writer.lock")), [])
                if not exists:
                    continue
                self.assertIn(operation, bootstrap[0].name)
                grant_raw = arguments.grant.read_bytes()
                grant = json.loads(grant_raw)
                self.assertIn(hashlib.sha256(grant_raw).hexdigest(), bootstrap[0].name)
                self.assertIn(hashlib.sha256(grant["nonce"].encode("ascii")).hexdigest(), bootstrap[0].name)
                if exact:
                    journal_raw = bootstrap[0].read_bytes()
                    self.assertEqual(
                        self.validator.validate_release_candidate_acquisition_record(
                            "operation_journal", journal_raw, self.policy
                        ),
                        [],
                    )
                    locator = f"journal:v1:{operation}:{hashlib.sha256(journal_raw).hexdigest()}"
                    output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
                    with (
                        mock.patch.object(self.engine.sys, "stdout", stdout),
                        mock.patch.object(self.engine.sys, "stderr", stderr),
                    ):
                        self.assertEqual(
                            self.engine.run(
                                SimpleNamespace(
                                    acquire_action="recover",
                                    recover_action="inspect",
                                    xdg_state_home=case / "state",
                                    journal_locator=locator,
                                ),
                                candidate=self.candidate,
                            ),
                            0,
                        )
                    self.assertEqual(json.loads(output.getvalue())["last_proven_phase"], "opened")
                elif exists:
                    locator = json.loads(errors.getvalue())["journal_locator"]
                    output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
                    with (
                        mock.patch.object(self.engine.sys, "stdout", stdout),
                        mock.patch.object(self.engine.sys, "stderr", stderr),
                    ):
                        self.assertEqual(
                            self.engine.run(
                                SimpleNamespace(
                                    acquire_action="recover",
                                    recover_action="inspect",
                                    xdg_state_home=case / "state",
                                    journal_locator=locator,
                                ),
                                candidate=self.candidate,
                            ),
                            4,
                        )
                    retained = json.loads(errors.getvalue())
                    self.assertEqual(retained["journal_locator"], locator)
                    self.assertEqual(retained["effect_state"], "unknown")

                before_replay = self._snapshot(case)
                with mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())):
                    replay = self.engine.run(
                        SimpleNamespace(acquire_action="apply", plan=arguments.plan, grant=arguments.grant),
                        candidate=self.candidate,
                    )
                self.assertEqual(replay, 3)
                self.assertEqual(self._snapshot(case), before_replay)

    def test_exact_opened_bootstrap_is_recoverable_without_prior_lifecycle_directories(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, operation, archive_sha = self._records(case)
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            def fault(point: str) -> None:
                if point == "first-after-parent-fsync":
                    raise RuntimeError("opened bootstrap crash")
            with (
                mock.patch.object(self.engine, "_TEST_FIRST_EFFECT_HOOK", fault),
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(
                    self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root),
                    4,
                )
            diagnostic = json.loads(errors.getvalue())
            locator = diagnostic["journal_locator"]
            bootstrap = next((case / "state").glob(".agentic-sdlc-acquisition-v1-*.opened.json"))
            self.assertFalse((case / "state" / "agentic-sdlc").exists())
            plan_raw = arguments.plan.read_bytes(); plan = json.loads(plan_raw)
            journal_raw = bootstrap.read_bytes()
            now = datetime.now(timezone.utc).replace(microsecond=0)
            grant = {
                "archive_absolute_path": plan["archive_absolute_path"], "archive_sha256": plan["archive_sha256"],
                "archive_size_bytes": plan["archive_size_bytes"], "decision": "finish",
                "effects_sha256": plan["effects_sha256"],
                "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "journal_absolute_physical_path": str(bootstrap), "journal_sha256": hashlib.sha256(journal_raw).hexdigest(),
                "nonce": "8" * 64, "operation_id": operation, "original_effects": list(self.engine.EFFECTS),
                "plan_sha256": hashlib.sha256(plan_raw).hexdigest(), "record_sha256": "",
                "same_user_uid": os.geteuid(), "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
                "trust_root_absolute_path": plan["trust_root_absolute_path"], "trust_root_sha256": plan["trust_root_sha256"],
                "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"], "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
                "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"], "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
            }
            recovery_grant = case / "opened-recovery-grant.json"
            recovery_grant.write_bytes(record_bytes(grant)); recovery_grant.chmod(0o600)
            output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.candidate, "validate_manifest"),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(
                    self.engine.recover_finish_hardened(
                        SimpleNamespace(
                            journal_locator=locator,
                            grant=recovery_grant,
                            xdg_state_home=case / "state",
                        ),
                        self.candidate,
                        self.policy,
                        self.validator,
                        self.source_root,
                    ),
                    0,
                )
            journal = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
            self.assertEqual(json.loads(journal.read_bytes())["entries"][-1]["phase"], "installed-unselected")
            self.assertTrue((case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha / "root").is_dir())
            self.assertFalse(any(case.rglob("writer.lock")))

    def test_foreign_stage_is_never_reused_or_erased(self) -> None:
        for kind in ("directory", "file", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, operation, archive_sha = self._records(case)
                staging = case / "data" / "agentic-sdlc" / "acquisition" / "staging"
                staging.mkdir(parents=True, mode=0o700)
                for directory in (
                    case / "data" / "agentic-sdlc",
                    case / "data" / "agentic-sdlc" / "acquisition",
                    staging,
                ):
                    directory.chmod(0o700)
                stage = staging / operation
                marker = case / "foreign-marker"
                marker.write_bytes(b"preserve-me\n")
                if kind == "directory":
                    stage.mkdir(mode=0o700)
                    (stage / "marker").write_bytes(b"preserve-me\n")
                elif kind == "file":
                    stage.write_bytes(b"preserve-me\n")
                else:
                    stage.symlink_to(marker)
                before = self._snapshot(case)
                with mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())):
                    result = self.engine.run(
                        SimpleNamespace(acquire_action="apply", plan=arguments.plan, grant=arguments.grant),
                        candidate=self.candidate,
                    )
                self.assertEqual(result, 3)
                self.assertEqual(self._snapshot(case), before)
                self.assertFalse((case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha).exists())
                self.assertFalse((case / "state" / "agentic-sdlc").exists())

        # A same-name directory appearing after the opened bootstrap is retained
        # as unknown; it is never adopted as this operation's stage.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, operation, archive_sha = self._records(case)
            marker_content = b"race-owned\n"
            def race(point: str) -> None:
                if point != "data-after-journal":
                    return
                stage = case / "data" / "agentic-sdlc" / "acquisition" / "staging" / operation
                stage.mkdir(mode=0o700)
                (stage / "marker").write_bytes(marker_content)
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.engine, "_TEST_RACE_HOOK", race),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                result = self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root)
            self.assertEqual(result, 4)
            stage = case / "data" / "agentic-sdlc" / "acquisition" / "staging" / operation
            self.assertEqual((stage / "marker").read_bytes(), marker_content)
            self.assertFalse((case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha).exists())

    def test_wrong_expired_and_cross_root_grants_refuse_before_any_target_effect(self) -> None:
        mutations = {
            "wrong-plan": lambda grant: grant.__setitem__("plan_sha256", "f" * 64),
            "cross-root": lambda grant: grant.__setitem__("xdg_state_home_absolute_path", "/wrong/state"),
            "expired": lambda grant: (
                grant.__setitem__("issued_at", "2020-01-01T00:00:00Z"),
                grant.__setitem__("expires_at", "2020-01-01T00:01:00Z"),
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw)
                arguments, _operation, _archive_sha = self._records(case)
                grant = json.loads(arguments.grant.read_bytes())
                mutate(grant)
                arguments.grant.write_bytes(record_bytes(grant))
                before = self._snapshot(case)
                output = io.BytesIO(); errors = io.BytesIO()
                stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
                stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
                with (
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                    mock.patch.object(self.engine.sys, "stdout", stdout),
                    mock.patch.object(self.engine.sys, "stderr", stderr),
                ):
                    result = self.engine.run(
                        SimpleNamespace(acquire_action="apply", plan=arguments.plan, grant=arguments.grant),
                        candidate=self.candidate,
                    )
                self.assertEqual(result, 3)
                self.assertEqual(self._snapshot(case), before)
                self.assertFalse((case / "state" / "agentic-sdlc").exists())
                self.assertFalse((case / "data" / "agentic-sdlc").exists())

    def test_descriptor_custody_refuses_child_symlink_before_effects_and_swap_after_journal(self) -> None:
        # A planted child redirect is a clean pre-effect refusal and cannot escape.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
            outside = case / "outside"; outside.mkdir(mode=0o700)
            (case / "data" / "agentic-sdlc").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())):
                with self.assertRaises(self.engine.AcquisitionFailure) as raised:
                    self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root)
            self.assertEqual(raised.exception.exit_code, 3)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((case / "state" / "agentic-sdlc").exists())

        # Lifecycle-directory creation is itself an admitted state effect. A state
        # namespace swap at that boundary is retained/unknown even though the journal
        # has not opened, and retained dirfds prevent escape into the replacement.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
            outside = case / "outside"; outside.mkdir(mode=0o700)
            def state_race(point: str) -> None:
                if point != "state-before-journal":
                    return
                acquisition = case / "state" / "agentic-sdlc" / "acquisition"
                held = acquisition.with_name("acquisition-held")
                acquisition.rename(held)
                acquisition.symlink_to(outside, target_is_directory=True)
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.engine, "_TEST_RACE_HOOK", state_race),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 4)
            diagnostic = json.loads(errors.getvalue())
            self.assertEqual(diagnostic["effect_state"], "unknown")
            self.assertEqual(diagnostic["last_proven_phase"], "opened")
            self.assertEqual(list(outside.iterdir()), [])

        # Once the journal is open, a same-UID namespace swap is retained exit 4; openat
        # custody prevents every subsequent write from reaching the substituted target.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, _operation, _archive_sha = self._records(case)
            outside = case / "outside"; outside.mkdir(mode=0o700)
            def race(point: str) -> None:
                if point != "data-after-journal":
                    return
                acquisition = case / "data" / "agentic-sdlc" / "acquisition"
                held = acquisition.with_name("acquisition-held")
                acquisition.rename(held)
                acquisition.symlink_to(outside, target_is_directory=True)
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.engine, "_TEST_RACE_HOOK", race),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 4)
            diagnostic = json.loads(errors.getvalue())
            self.assertEqual(diagnostic["effect_state"], "unknown")
            self.assertEqual(diagnostic["last_proven_phase"], "opened")
            self.assertEqual(list(outside.iterdir()), [])

    def test_exact_rerun_preserves_and_refuses_every_installed_evidence_mutation(self) -> None:
        mutations = {
            "executable": lambda final, journal, receipt: (final / "root" / "runtime" / "python" / "bin" / "python3.12").write_bytes(b"changed\n"),
            "acquisition-module": lambda final, journal, receipt: (final / "root" / "scripts" / "release_candidate_acquisition.py").write_bytes(b"changed\n"),
            "added-file": lambda final, journal, receipt: (final / "root" / "added").write_bytes(b"foreign\n"),
            "removed-file": lambda final, journal, receipt: (final / "root" / "scripts" / "release_candidate.py").unlink(),
            "symlink": lambda final, journal, receipt: (final / "root" / "foreign-link").symlink_to("manifest.json"),
            "archive": lambda final, journal, receipt: (final / "candidate.tar.gz").write_bytes(b"changed archive\n"),
            "journal": lambda final, journal, receipt: journal.write_bytes(journal.read_bytes() + b"x"),
            "receipt": lambda final, journal, receipt: receipt.write_bytes(receipt.read_bytes() + b"x"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, operation, archive_sha = self._records(case)
                trust_sha = hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest()
                with (
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", trust_sha)),
                    mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                ):
                    self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 0)
                final = case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha
                journal = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
                receipt = case / "state" / "agentic-sdlc" / "acquisition" / "receipts" / f"{archive_sha}.json"
                mutate(final, journal, receipt)
                before = self._snapshot(case)
                with (
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", trust_sha)),
                    mock.patch.object(self.candidate, "validate_manifest"),
                    self.assertRaises(self.engine.AcquisitionFailure) as raised,
                ):
                    self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root)
                self.assertEqual(raised.exception.exit_code, 3)
                self.assertEqual(self._snapshot(case), before)

    def test_apply_is_journal_first_publishes_no_replace_receipt_and_exact_rerun_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            arguments, operation, archive_sha = self._records(case)
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 0)
            self.assertEqual(errors.getvalue(), b"")
            state_root = case / "state" / "agentic-sdlc" / "acquisition"
            data_root = case / "data" / "agentic-sdlc" / "acquisition"
            journal_path = state_root / "journals" / f"{operation}.json"
            journal_raw = journal_path.read_bytes()
            journal = json.loads(journal_raw)
            self.assertEqual([entry["phase"] for entry in journal["entries"]], self.engine.PHASES)
            self.assertEqual(self.validator.validate_release_candidate_acquisition_record("operation_journal", journal_raw, self.policy), [])
            receipt = state_root / "receipts" / f"{archive_sha}.json"
            self.assertTrue(receipt.is_file())
            self.assertTrue((data_root / "candidates" / archive_sha / "root").is_dir())
            self.assertFalse((data_root / "staging" / operation).exists())
            self.assertFalse(any(data_root.rglob("current")))
            self.assertFalse(any(data_root.rglob("channel")))

            before = {str(path.relative_to(case)): (path.lstat().st_ino, path.lstat().st_mtime_ns, path.read_bytes() if path.is_file() else None) for path in case.rglob("*")}
            output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                mock.patch.object(self.candidate, "validate_manifest"),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 0)
            after = {str(path.relative_to(case)): (path.lstat().st_ino, path.lstat().st_mtime_ns, path.read_bytes() if path.is_file() else None) for path in case.rglob("*")}
            self.assertEqual(after, before)

    def test_fault_after_each_durable_phase_returns_four_and_preserves_exact_journal(self) -> None:
        for fault_phase in self.engine.PHASES:
            with self.subTest(phase=fault_phase), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw)
                arguments, operation, _archive_sha = self._records(case)
                output = io.BytesIO(); errors = io.BytesIO()
                stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
                stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
                def fault(phase: str) -> None:
                    if phase == fault_phase: raise RuntimeError("test fault")
                with (
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                    mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                    mock.patch.object(self.engine, "_TEST_FAULT_HOOK", fault),
                    mock.patch.object(self.engine.sys, "stdout", stdout),
                    mock.patch.object(self.engine.sys, "stderr", stderr),
                ):
                    result = self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root)
                if fault_phase == "installed-unselected":
                    self.assertEqual(result, 0)
                    self.assertEqual(errors.getvalue(), b"")
                else:
                    self.assertEqual(result, 4)
                    diagnostic = json.loads(errors.getvalue())
                    self.assertIn(diagnostic["effect_state"], {"partial", "unknown"})
                    self.assertEqual(diagnostic["last_proven_phase"], fault_phase)
                    self.assertEqual(len(diagnostic["next_action"]), 7)
                journal_path = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
                self.assertTrue(journal_path.is_file())
                journal_raw = journal_path.read_bytes()
                self.assertEqual(self.validator.validate_release_candidate_acquisition_record("operation_journal", journal_raw, self.policy), [])
                self.assertEqual(json.loads(journal_raw)["entries"][-1]["phase"], fault_phase)

    def test_a_text_stderr_costs_apply_neither_its_exit_code_nor_its_diagnostic(self) -> None:
        """The four `sys.stderr.buffer` sites were the error reporter dying while reporting an error.

        A text `sys.stderr` has no `.buffer`, and `unittest --buffer` and
        `contextlib.redirect_stderr(io.StringIO())` each install exactly that, so an in-process
        caller reached `AttributeError` INSIDE the `except` handlers below: the exit-4 diagnostic was
        never delivered and the code became `run`'s generic 1 — a partial effect reported as a clean
        pre-effect internal failure. Both handlers are exercised: an `AcquisitionFailure` raised past
        the first durable effect (exact/partial) and an unexpected `RuntimeError` (unavailable/
        unknown), because they build different diagnostics and only the specific one is evidence.
        """
        trust = ROOT / "policy" / "release-candidate.v1.json"

        def staged_fault(phase: str) -> None:
            # `_fault_after_phase` turns any hook exception into an exact `AcquisitionFailure`, so
            # this reaches the FIRST handler and never the second.
            if phase == "staged":
                raise RuntimeError("test-injected fault at the staged boundary")

        shapes = {
            # (extra injection, expected classification, expected effect_state)
            "acquisition-failure": (
                lambda: mock.patch.object(self.engine, "_TEST_FAULT_HOOK", staged_fault),
                "exact",
                "partial",
            ),
            "unexpected-exception": (
                # A genuine non-`AcquisitionFailure` escaping the body after the staged journal is
                # durable, which is the ONLY way to reach the `except Exception` handler.
                lambda: mock.patch.object(
                    self.engine,
                    "_rename_noreplace_at",
                    side_effect=RuntimeError("test-injected internal after staged"),
                ),
                "unavailable",
                "unknown",
            ),
        }

        def run_apply(case: Path, sink: object, inject) -> tuple[int, str]:
            arguments, operation, _archive_sha = self._records(case)
            with contextlib.ExitStack() as stack:
                for patcher in (
                    mock.patch.object(
                        self.engine,
                        "_trust_root",
                        return_value=(trust, hashlib.sha256(trust.read_bytes()).hexdigest()),
                    ),
                    mock.patch.object(
                        self.engine, "_stage_candidate", side_effect=self._fake_stage
                    ),
                    inject(),
                    mock.patch.object(self.engine.sys, "stderr", sink),
                ):
                    stack.enter_context(patcher)
                return (
                    self.engine.apply_hardened(
                        arguments, self.candidate, self.policy, self.validator, self.source_root
                    ),
                    operation,
                )

        def comparable(record: dict[str, object]) -> dict[str, object]:
            """Everything two runs of the same injection must agree on.

            `journal_locator` embeds the journal digest and `record_sha256` seals the record, so both
            legitimately differ between two runs over two state roots; their SHAPE is asserted
            separately rather than dropped.
            """
            return {k: v for k, v in record.items() if k not in {"journal_locator", "record_sha256"}}

        for label, (inject, classification, effect_state) in shapes.items():
            with self.subTest(shape=label), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw)
                text = io.StringIO()
                result, operation = run_apply(case, text, inject)
                self.assertEqual(result, 4)  # not 1, and not an escaping AttributeError
                diagnostic = json.loads(text.getvalue())
                self.assertEqual(
                    diagnostic["schema_version"],
                    "release-candidate-acquisition-exit4-diagnostic/v1",
                )
                self.assertEqual(diagnostic["classification"], classification)
                self.assertEqual(diagnostic["effect_state"], effect_state)
                self.assertEqual(diagnostic["last_proven_phase"], "staged")
                self.assertEqual(diagnostic["operation_id"], operation)
                self.assertRegex(diagnostic["journal_locator"], r"^journal:v1:op-[0-9a-f]{32}:[0-9a-f]{64}$")
                journal = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
                self.assertTrue(journal.is_file())  # the durable artifact is untouched by all this
                # POSITIVE CONTROL: the same injection over a BYTE stderr reports the same record, so
                # the text path above lost nothing and this channel really does carry the value.
                with tempfile.TemporaryDirectory(dir=ROOT) as raw_control:
                    errors = io.BytesIO()
                    stderr = SimpleNamespace(
                        buffer=errors, write=lambda t: errors.write(t.encode("utf-8"))
                    )
                    control_result, _operation = run_apply(Path(raw_control), stderr, inject)
                self.assertEqual(control_result, 4)
                self.assertEqual(
                    comparable(json.loads(errors.getvalue())), comparable(diagnostic)
                )
                self.assertRegex(
                    json.loads(errors.getvalue())["journal_locator"],
                    r"^journal:v1:op-[0-9a-f]{32}:[0-9a-f]{64}$",
                )

    def test_an_unwritable_stderr_costs_apply_only_its_diagnostic(self) -> None:
        """A sink that FAILS mid-write is the second shape, and it may cost only the display.

        Settling the shape cannot help here: the write fails for a reason no shape check can see. So
        the exit code, the journal, and the receipt-bearing state on disk must all survive it, and
        the failed stream is dropped so the interpreter's shutdown flush cannot replace the code
        with CPython's 120.
        """
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            arguments, operation, _archive_sha = self._records(case)
            trust = ROOT / "policy" / "release-candidate.v1.json"

            def fault(phase: str) -> None:
                if phase == "staged":
                    raise RuntimeError("test-injected internal")

            broken = SimpleNamespace(
                buffer=mock.Mock(**{"write.side_effect": OSError(errno.EPIPE, "broken pipe")}),
                write=lambda text: None,
            )
            with (
                mock.patch.object(
                    self.engine,
                    "_trust_root",
                    return_value=(trust, hashlib.sha256(trust.read_bytes()).hexdigest()),
                ),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.engine, "_TEST_FAULT_HOOK", fault),
                mock.patch.object(self.engine.sys, "stderr", broken),
            ):
                result = self.engine.apply_hardened(
                    arguments, self.candidate, self.policy, self.validator, self.source_root
                )
                # POSITIVE CONTROL on the injection: the sink was REACHED and it DID fail. Without
                # this, the assertions below would also pass on a run that never wrote a byte.
                self.assertTrue(broken.buffer.write.called)
                self.assertIsNone(sys.stderr)  # the stream that failed was dropped, not kept
            self.assertEqual(result, 4)
            journal = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
            self.assertTrue(journal.is_file())
            self.assertEqual(
                self.validator.validate_release_candidate_acquisition_record(
                    "operation_journal", journal.read_bytes(), self.policy
                ),
                [],
            )

    def test_recover_finish_reports_its_exit4_reason_onto_a_text_stderr(self) -> None:
        """The third site, in `recover_finish_hardened`, reached through its own `except` handler."""
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            state = case / "state"
            state.mkdir(mode=0o700)
            locator = f"journal:v1:op-{'0' * 32}:{'c' * 64}"
            arguments = SimpleNamespace(
                acquire_action="recover",
                recover_action="finish",
                xdg_state_home=state,
                journal_locator=locator,
                grant=case / "grant.json",
            )
            injected = self.engine.AcquisitionFailure(
                "test-injected-journal",
                4,
                f"op-{'0' * 32}",
                locator,
                "published",
                "exact",
            )
            text = io.StringIO()
            with (
                mock.patch.object(self.engine, "_load_journal_at", side_effect=injected),
                mock.patch.object(self.engine.sys, "stderr", text),
            ):
                result = self.engine.recover_finish_hardened(
                    arguments, self.candidate, self.policy, self.validator, self.source_root
                )
            self.assertEqual(result, 4)
            diagnostic = json.loads(text.getvalue())
            self.assertEqual(
                diagnostic["schema_version"], "release-candidate-acquisition-exit4-diagnostic/v1"
            )
            self.assertEqual(diagnostic["last_proven_phase"], "published")
            self.assertEqual(diagnostic["effect_state"], "partial")
            self.assertEqual(diagnostic["journal_locator"], locator)
            # POSITIVE CONTROL: the byte-stderr shape yields the identical bytes, so the text sink
            # above is a translation of a live channel and not an empty one.
            errors = io.BytesIO()
            stderr = SimpleNamespace(buffer=errors, write=lambda t: errors.write(t.encode("utf-8")))
            with (
                mock.patch.object(self.engine, "_load_journal_at", side_effect=injected),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                control = self.engine.recover_finish_hardened(
                    arguments, self.candidate, self.policy, self.validator, self.source_root
                )
            self.assertEqual(control, 4)
            self.assertEqual(errors.getvalue(), text.getvalue().encode("utf-8"))

    def test_receipt_publication_crash_window_is_exactly_idempotent(self) -> None:
        points = {
            "receipt-before-create": "absent",
            "receipt-after-create": "foreign",
            "receipt-after-write": "exact",
            "receipt-after-file-fsync": "exact",
            "receipt-after-parent-fsync": "exact",
            "receipt-before-receipted": "exact",
        }
        for point, receipt_state in points.items():
            with self.subTest(point=point), tempfile.TemporaryDirectory(dir=ROOT) as raw:
                case = Path(raw); arguments, operation, archive_sha = self._records(case)
                output = io.BytesIO(); errors = io.BytesIO()
                stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
                stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
                def receipt_fault(actual: str) -> None:
                    if actual == point:
                        raise RuntimeError("receipt crash")
                with (
                    mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest())),
                    mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                    mock.patch.object(self.engine, "_TEST_RECEIPT_HOOK", receipt_fault),
                    mock.patch.object(self.engine.sys, "stdout", stdout),
                    mock.patch.object(self.engine.sys, "stderr", stderr),
                ):
                    self.assertEqual(
                        self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root),
                        4,
                    )
                diagnostic = json.loads(errors.getvalue())
                self.assertEqual(diagnostic["last_proven_phase"], "published")
                locator = diagnostic["journal_locator"]
                journal_path = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
                receipt_path = case / "state" / "agentic-sdlc" / "acquisition" / "receipts" / f"{archive_sha}.json"
                self.assertEqual(receipt_path.exists(), receipt_state != "absent")
                if receipt_state == "foreign":
                    self.assertEqual(receipt_path.read_bytes(), b"")

                plan_raw = arguments.plan.read_bytes(); plan = json.loads(plan_raw)
                journal_raw = journal_path.read_bytes()
                now = datetime.now(timezone.utc).replace(microsecond=0)
                grant = {
                    "archive_absolute_path": plan["archive_absolute_path"], "archive_sha256": plan["archive_sha256"],
                    "archive_size_bytes": plan["archive_size_bytes"], "decision": "finish",
                    "effects_sha256": plan["effects_sha256"],
                    "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "journal_absolute_physical_path": str(journal_path), "journal_sha256": hashlib.sha256(journal_raw).hexdigest(),
                    "nonce": "d" * 64, "operation_id": operation, "original_effects": list(self.engine.EFFECTS),
                    "plan_sha256": hashlib.sha256(plan_raw).hexdigest(), "record_sha256": "",
                    "same_user_uid": os.geteuid(), "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
                    "trust_root_absolute_path": plan["trust_root_absolute_path"], "trust_root_sha256": plan["trust_root_sha256"],
                    "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"], "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
                    "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"], "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
                }
                recovery_grant = case / "receipt-recovery-grant.json"
                recovery_grant.write_bytes(record_bytes(grant)); recovery_grant.chmod(0o600)
                finish_args = SimpleNamespace(
                    journal_locator=locator,
                    grant=recovery_grant,
                    xdg_state_home=case / "state",
                )
                private_root = case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha / "root"
                receipt_inode = receipt_path.stat().st_ino if receipt_state == "exact" else None
                output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
                with (
                    mock.patch.object(self.candidate, "validate_manifest"),
                    mock.patch.object(self.engine.sys, "stdout", stdout),
                    mock.patch.object(self.engine.sys, "stderr", stderr),
                ):
                    result = self.engine.recover_finish_hardened(
                        finish_args,
                        self.candidate,
                        self.policy,
                        self.validator,
                        private_root,
                    )
                if receipt_state == "foreign":
                    self.assertEqual(result, 4)
                    self.assertEqual(receipt_path.read_bytes(), b"")
                    self.assertEqual(json.loads(journal_path.read_bytes())["entries"][-1]["phase"], "published")
                else:
                    self.assertEqual(result, 0)
                    self.assertEqual(json.loads(journal_path.read_bytes())["entries"][-1]["phase"], "installed-unselected")
                    if receipt_inode is not None:
                        self.assertEqual(receipt_path.stat().st_ino, receipt_inode)

    def _exact_receipt_crash_window(
        self, case: Path, *, nonce: str
    ) -> tuple[SimpleNamespace, str, str, Path, Path, Path]:
        """Leave apply's exact receipt on disk with the journal still at `published`.

        That is the ONE durable state that reaches recover finish's "make these exact bytes
        durable in place" branch, so it is the state a forgery of those bytes has to be
        attacked from. The clean version of this window is already covered above: at
        `receipt-before-receipted` an untouched receipt recovers to exit 0 on the same inode.
        """
        arguments, operation, archive_sha = self._records(case)
        output = io.BytesIO()
        errors = io.BytesIO()
        stdout = SimpleNamespace(
            buffer=output, write=lambda text: output.write(text.encode("utf-8"))
        )
        stderr = SimpleNamespace(
            buffer=errors, write=lambda text: errors.write(text.encode("utf-8"))
        )

        def receipt_fault(point: str) -> None:
            if point == "receipt-before-receipted":
                raise RuntimeError("receipt crash")

        trust = ROOT / "policy" / "release-candidate.v1.json"
        with (
            mock.patch.object(
                self.engine,
                "_trust_root",
                return_value=(trust, hashlib.sha256(trust.read_bytes()).hexdigest()),
            ),
            mock.patch.object(
                self.engine, "_stage_candidate", side_effect=self._fake_stage
            ),
            mock.patch.object(self.engine, "_TEST_RECEIPT_HOOK", receipt_fault),
            mock.patch.object(self.engine.sys, "stdout", stdout),
            mock.patch.object(self.engine.sys, "stderr", stderr),
        ):
            self.assertEqual(
                self.engine.apply_hardened(
                    arguments,
                    self.candidate,
                    self.policy,
                    self.validator,
                    self.source_root,
                ),
                4,
            )
        diagnostic = json.loads(errors.getvalue())
        self.assertEqual(diagnostic["last_proven_phase"], "published")
        journal_path = (
            case
            / "state"
            / "agentic-sdlc"
            / "acquisition"
            / "journals"
            / f"{operation}.json"
        )
        receipt_path = self._receipt(case, archive_sha)
        self.assertTrue(receipt_path.is_file())
        plan_raw = arguments.plan.read_bytes()
        plan = json.loads(plan_raw)
        journal_raw = journal_path.read_bytes()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        grant = {
            "archive_absolute_path": plan["archive_absolute_path"],
            "archive_sha256": plan["archive_sha256"],
            "archive_size_bytes": plan["archive_size_bytes"],
            "decision": "finish",
            "effects_sha256": plan["effects_sha256"],
            "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "journal_absolute_physical_path": str(journal_path),
            "journal_sha256": hashlib.sha256(journal_raw).hexdigest(),
            "nonce": nonce,
            "operation_id": operation,
            "original_effects": list(self.engine.EFFECTS),
            "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
            "record_sha256": "",
            "same_user_uid": os.geteuid(),
            "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
            "trust_root_absolute_path": plan["trust_root_absolute_path"],
            "trust_root_sha256": plan["trust_root_sha256"],
            "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"],
            "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
            "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"],
            "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
        }
        recovery_grant = case / "receipt-readback-grant.json"
        recovery_grant.write_bytes(record_bytes(grant))
        recovery_grant.chmod(0o600)
        return (
            SimpleNamespace(
                journal_locator=diagnostic["journal_locator"],
                grant=recovery_grant,
                xdg_state_home=case / "state",
            ),
            operation,
            archive_sha,
            receipt_path,
            journal_path,
            case
            / "data"
            / "agentic-sdlc"
            / "acquisition"
            / "candidates"
            / archive_sha
            / "root",
        )

    @staticmethod
    def _forged_same_length_receipt(raw: bytes) -> bytes:
        """A different receipt of identical length: canonical, resealed, journal digest kept.

        Keeping `journal_sha256` is the point. It is the only field the readback used to
        compare, so a forgery that preserves it passed while every other field — the
        `archive_sha256` this receipt exists to assert above all — was the attacker's.
        """
        record = json.loads(raw)
        assert record["archive_sha256"] != "f" * 64
        record["archive_sha256"] = "f" * 64
        forged = record_bytes(record)
        assert len(forged) == len(raw) and forged != raw
        return forged

    def _recover_finish_with_receipt_racer(
        self,
        engine,
        finish_args: SimpleNamespace,
        receipt_path: Path,
        private_root: Path,
        *,
        real_identity: bool,
    ) -> SimpleNamespace:
        """Recover the receipt window with a racer inside `_sync_existing_at`'s blind spot.

        The racer fires immediately after the `receipt-existing` read the caller compares
        against, which is exactly where a same-UID writer would land: `_sync_existing_at`
        then opens the file fresh, takes its `before` stat AFTER the write, and fsyncs the
        forgery. No timestamp term is involved on either arm, which is why both are run.
        """
        codes: list[str] = []
        real_fail = engine._fail
        real_read_at = engine._read_at
        forged: dict[str, object] = {}

        def recording_fail(code: str, exit_code: int = 3, **evidence: object) -> None:
            codes.append(code)
            real_fail(code, exit_code, **evidence)

        def racing_read_at(parent, name, limit, code, **keywords):
            raw = real_read_at(parent, name, limit, code, **keywords)
            if code == "receipt-existing":
                replacement = self._forged_same_length_receipt(raw)
                descriptor = os.open(receipt_path, os.O_WRONLY)
                try:
                    os.pwrite(descriptor, replacement, 0)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                forged["raw"] = replacement
                forged["inode"] = receipt_path.stat().st_ino
            return raw

        output = io.BytesIO()
        errors = io.BytesIO()
        stdout = SimpleNamespace(
            buffer=output, write=lambda text: output.write(text.encode("utf-8"))
        )
        stderr = SimpleNamespace(
            buffer=errors, write=lambda text: errors.write(text.encode("utf-8"))
        )
        with (
            mock.patch.object(
                engine,
                "_identity",
                engine._identity if real_identity else self._timestamp_free_identity,
            ),
            mock.patch.object(engine, "_fail", recording_fail),
            mock.patch.object(engine, "_read_at", racing_read_at),
            mock.patch.object(self.candidate, "validate_manifest"),
            mock.patch.object(engine.sys, "stdout", stdout),
            mock.patch.object(engine.sys, "stderr", stderr),
        ):
            result = engine.recover_finish_hardened(
                finish_args,
                self.candidate,
                self.policy,
                self.validator,
                private_root,
            )
        return SimpleNamespace(
            result=result,
            codes=codes,
            forged=forged,
            stdout=output.getvalue(),
            stderr=errors.getvalue(),
        )

    def test_receipt_readback_refuses_a_forged_pre_fsync_receipt_on_either_clock(
        self,
    ) -> None:
        for real_identity in (False, True):
            with (
                self.subTest(real_identity=real_identity),
                tempfile.TemporaryDirectory(dir=ROOT) as raw,
            ):
                case = Path(raw)
                (
                    finish_args,
                    _operation,
                    archive_sha,
                    receipt_path,
                    journal_path,
                    private_root,
                ) = self._exact_receipt_crash_window(
                    case, nonce="c" * 64 if real_identity else "d" * 64
                )
                admitted_receipt = receipt_path.read_bytes()
                inode = receipt_path.stat().st_ino
                run = self._recover_finish_with_receipt_racer(
                    self.engine,
                    finish_args,
                    receipt_path,
                    private_root,
                    real_identity=real_identity,
                )
                self.assertEqual(run.result, 4)
                self.assertEqual(run.codes, ["receipt-readback"])
                self.assertEqual(run.stdout, b"")
                self.assertEqual(
                    json.loads(run.stderr)["classification"], "unavailable"
                )
                # The forgery really did land, in place, on the same immutable receipt.
                self.assertEqual(receipt_path.read_bytes(), run.forged["raw"])
                self.assertNotEqual(run.forged["raw"], admitted_receipt)
                self.assertEqual(
                    (run.forged["inode"], receipt_path.stat().st_ino), (inode, inode)
                )
                self.assertEqual(json.loads(run.forged["raw"])["archive_sha256"], "f" * 64)
                # Refused BEFORE the terminal transition, so nothing claims a complete effect.
                self.assertEqual(json.loads(run.stderr)["effect_state"], "unknown")
                self.assertEqual(
                    json.loads(journal_path.read_bytes())["entries"][-1]["phase"],
                    "receipted",
                )
                self.assertEqual(archive_sha, json.loads(admitted_receipt)["archive_sha256"])

        # Positive control: the FULL-byte comparison is what refuses, not the harness and not
        # a clock. Neutralized in a scratch copy of the engine, the same forgery is fsynced by
        # the engine itself and returned as a complete effect — the accepted verdict this
        # closes — while the one field the readback used to compare still agrees.
        guard = "if receipt_raw_readback != receipt_raw:"
        source = ENGINE_PATH.read_text(encoding="utf-8")
        self.assertIn(guard, source)
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            (
                finish_args,
                _operation,
                _archive_sha,
                receipt_path,
                journal_path,
                private_root,
            ) = self._exact_receipt_crash_window(case, nonce="e" * 64)
            admitted_receipt = receipt_path.read_bytes()
            scratch = case / "release_candidate_acquisition_without_the_readback.py"
            scratch.write_text(
                source.replace(guard, "if False:  # readback neutralized"),
                encoding="utf-8",
            )
            neutralized = load_module(
                "release_candidate_acquisition_readback_neutralized_under_test", scratch
            )
            run = self._recover_finish_with_receipt_racer(
                neutralized,
                finish_args,
                receipt_path,
                private_root,
                real_identity=True,
            )
            self.assertEqual((run.result, run.codes), (0, []))
            durable = json.loads(receipt_path.read_bytes())
            self.assertEqual(durable["archive_sha256"], "f" * 64)
            self.assertEqual(
                durable["journal_sha256"],
                json.loads(admitted_receipt)["journal_sha256"],
            )
            self.assertEqual(
                json.loads(journal_path.read_bytes())["entries"][-1]["phase"],
                "installed-unselected",
            )

    def test_recovery_inspect_is_read_only_and_separately_granted_private_finish_advances_staged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            arguments, operation, archive_sha = self._records(case)
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            def fault(phase: str) -> None:
                if phase == "staged": raise RuntimeError("staged boundary")
            trust_sha = hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest()
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", trust_sha)),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.engine, "_TEST_FAULT_HOOK", fault),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 4)
            diagnostic = json.loads(errors.getvalue())
            locator = diagnostic["journal_locator"]
            state_root = case / "state" / "agentic-sdlc" / "acquisition"
            journal_path = state_root / "journals" / f"{operation}.json"

            before = {str(path.relative_to(case)): (path.lstat().st_ino, path.lstat().st_mtime_ns, path.read_bytes() if path.is_file() else None) for path in case.rglob("*")}
            output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
            recover_inspect_args = SimpleNamespace(
                journal_locator=locator, xdg_state_home=case / "state"
            )
            with mock.patch.object(self.engine.sys, "stdout", stdout), mock.patch.object(self.engine.sys, "stderr", stderr):
                self.assertEqual(self.engine.recover_inspect_hardened(recover_inspect_args, self.candidate, self.policy, self.validator), 0)
            after = {str(path.relative_to(case)): (path.lstat().st_ino, path.lstat().st_mtime_ns, path.read_bytes() if path.is_file() else None) for path in case.rglob("*")}
            self.assertEqual(after, before)
            self.assertEqual(
                json.loads(output.getvalue())["next_action"][:4],
                ["acquire", "recover", "finish", "--xdg-state-home"],
            )

            plan_raw = arguments.plan.read_bytes(); plan = json.loads(plan_raw)
            journal_raw = journal_path.read_bytes()
            now = datetime.now(timezone.utc).replace(microsecond=0)
            grant = {
                "archive_absolute_path": plan["archive_absolute_path"], "archive_sha256": plan["archive_sha256"],
                "archive_size_bytes": plan["archive_size_bytes"], "decision": "finish",
                "effects_sha256": plan["effects_sha256"],
                "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "journal_absolute_physical_path": str(journal_path), "journal_sha256": hashlib.sha256(journal_raw).hexdigest(),
                "nonce": "c" * 64, "operation_id": operation, "original_effects": list(self.engine.EFFECTS),
                "plan_sha256": hashlib.sha256(plan_raw).hexdigest(), "record_sha256": "",
                "same_user_uid": os.geteuid(), "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
                "trust_root_absolute_path": plan["trust_root_absolute_path"], "trust_root_sha256": plan["trust_root_sha256"],
                "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"], "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
                "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"], "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
            }
            recovery_grant = case / "recovery-grant.json"
            recovery_grant.write_bytes(record_bytes(grant)); recovery_grant.chmod(0o600)
            private_python = case / "data" / "agentic-sdlc" / "acquisition" / "staging" / operation / "root" / "runtime" / "python" / "bin" / "python3.12"
            output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
            finish_args = SimpleNamespace(
                journal_locator=locator,
                grant=recovery_grant,
                xdg_state_home=case / "state",
            )
            with (
                mock.patch.object(self.candidate, "validate_manifest"),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(
                    self.engine.recover_finish_hardened(
                        finish_args,
                        self.candidate,
                        self.policy,
                        self.validator,
                        private_python.parents[3],
                    ),
                    0,
                )
            self.assertEqual(errors.getvalue(), b"")
            final_journal = journal_path.read_bytes()
            self.assertEqual(self.validator.validate_release_candidate_acquisition_record("operation_journal", final_journal, self.policy), [])
            self.assertEqual(json.loads(final_journal)["entries"][-1]["phase"], "installed-unselected")
            self.assertTrue((case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha / "root").is_dir())
            self.assertTrue((state_root / "receipts" / f"{archive_sha}.json").is_file())

    def test_outer_recovery_rejects_candidate_forged_terminal_without_receipt_or_final_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw); arguments, operation, archive_sha = self._records(case)
            trust_sha = hashlib.sha256((ROOT / "policy" / "release-candidate.v1.json").read_bytes()).hexdigest()
            output = io.BytesIO(); errors = io.BytesIO()
            stdout = SimpleNamespace(buffer=output, write=lambda text: output.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=errors, write=lambda text: errors.write(text.encode("utf-8")))
            def fault(phase: str) -> None:
                if phase == "staged": raise RuntimeError("staged")
            with (
                mock.patch.object(self.engine, "_trust_root", return_value=(ROOT / "policy" / "release-candidate.v1.json", trust_sha)),
                mock.patch.object(self.engine, "_stage_candidate", side_effect=self._fake_stage),
                mock.patch.object(self.engine, "_TEST_FAULT_HOOK", fault),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.apply_hardened(arguments, self.candidate, self.policy, self.validator, self.source_root), 4)
            locator = json.loads(errors.getvalue())["journal_locator"]
            journal_path = case / "state" / "agentic-sdlc" / "acquisition" / "journals" / f"{operation}.json"
            plan_raw = arguments.plan.read_bytes(); plan = json.loads(plan_raw)
            now = datetime.now(timezone.utc).replace(microsecond=0)
            grant = {
                "archive_absolute_path": plan["archive_absolute_path"], "archive_sha256": plan["archive_sha256"],
                "archive_size_bytes": plan["archive_size_bytes"], "decision": "finish",
                "effects_sha256": plan["effects_sha256"],
                "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "journal_absolute_physical_path": str(journal_path), "journal_sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest(),
                "nonce": "9" * 64, "operation_id": operation, "original_effects": list(self.engine.EFFECTS),
                "plan_sha256": hashlib.sha256(plan_raw).hexdigest(), "record_sha256": "",
                "same_user_uid": os.geteuid(), "schema_version": "release-candidate-acquisition-recover-finish-grant/v1",
                "trust_root_absolute_path": plan["trust_root_absolute_path"], "trust_root_sha256": plan["trust_root_sha256"],
                "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"], "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
                "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"], "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
            }
            recovery_grant = case / "recovery-grant.json"
            recovery_grant.write_bytes(record_bytes(grant)); recovery_grant.chmod(0o600)
            root = case / "data" / "agentic-sdlc" / "acquisition" / "staging" / operation / "root"
            module_path = root / "scripts" / "release_candidate_acquisition.py"
            original_module = module_path.read_bytes()
            module_path.write_bytes(b"pre-child mutation\n")
            output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
            with (
                mock.patch.object(self.candidate, "validate_manifest"),
                mock.patch.object(self.engine.subprocess, "run") as child,
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(
                    self.engine.recover_finish_hardened(
                        SimpleNamespace(xdg_state_home=case / "state", journal_locator=locator, grant=recovery_grant),
                        self.candidate, self.policy, self.validator, self.source_root,
                    ),
                    4,
                )
            child.assert_not_called()
            module_path.write_bytes(original_module)

            def forged_child(*_args, **_kwargs):
                operation_journal = json.loads(journal_path.read_bytes())
                entries = operation_journal["entries"]
                terminal = entries[-1]
                plan_projection = {
                    "archive_absolute_path": grant["archive_absolute_path"],
                    "archive_sha256": grant["archive_sha256"],
                    "archive_size_bytes": grant["archive_size_bytes"],
                    "effects_sha256": grant["effects_sha256"],
                }
                self.engine._append_entry(operation, plan_projection, grant["plan_sha256"], entries, "published", terminal["candidate_root_sha256"], terminal["interpreter_sha256"])
                _receipted, _receipted_raw, _terminal, terminal_raw = self.engine._planned_terminal_journals(
                    operation, plan_projection, grant["plan_sha256"], entries,
                    terminal["candidate_root_sha256"], terminal["interpreter_sha256"],
                )
                journal_path.write_bytes(terminal_raw)
                module_path.write_bytes(b"post-child mutation\n")
                return subprocess.CompletedProcess([], 0, stdout=b'{"forged":true}\n', stderr=b"")
            output.seek(0); output.truncate(); errors.seek(0); errors.truncate()
            with (
                mock.patch.object(self.candidate, "validate_manifest"),
                mock.patch.object(self.engine.subprocess, "run", side_effect=forged_child),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(
                    self.engine.recover_finish_hardened(
                        SimpleNamespace(xdg_state_home=case / "state", journal_locator=locator, grant=recovery_grant),
                        self.candidate, self.policy, self.validator, self.source_root,
                    ),
                    4,
                )
            diagnostic = json.loads(errors.getvalue())
            self.assertEqual(diagnostic["effect_state"], "unknown")
            self.assertFalse((case / "state" / "agentic-sdlc" / "acquisition" / "receipts" / f"{archive_sha}.json").exists())
            self.assertFalse((case / "data" / "agentic-sdlc" / "acquisition" / "candidates" / archive_sha).exists())
            self.assertEqual(module_path.read_bytes(), b"post-child mutation\n")

    def test_private_recovery_timeout_is_exit4_unknown_with_bounded_action(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            finish_args, operation, archive_sha, locator, journal_path = (
                self._staged_recovery_case(case, nonce="7" * 64)
            )
            before = self._snapshot(case)
            journal_before = journal_path.read_bytes()
            output = io.BytesIO()
            errors = io.BytesIO()
            stdout = SimpleNamespace(
                buffer=output,
                write=lambda text: output.write(text.encode("utf-8")),
            )
            stderr = SimpleNamespace(
                buffer=errors,
                write=lambda text: errors.write(text.encode("utf-8")),
            )
            timeout = subprocess.TimeoutExpired(
                cmd=["credential-canary-private-python"],
                timeout=120,
                output=b"credential-canary-output",
                stderr=b"credential-canary-error",
            )
            with (
                mock.patch.object(self.candidate, "validate_manifest"),
                mock.patch.object(self.engine.subprocess, "run", side_effect=timeout),
                mock.patch.object(self.engine.sys, "stdout", stdout),
                mock.patch.object(self.engine.sys, "stderr", stderr),
            ):
                self.assertEqual(self.engine.run(finish_args, candidate=self.candidate), 4)

            self.assertEqual(output.getvalue(), b"")
            diagnostic = json.loads(errors.getvalue())
            self.assertEqual(
                errors.getvalue(),
                canonical(diagnostic),
            )
            self.assertEqual(
                diagnostic["schema_version"],
                "release-candidate-acquisition-exit4-diagnostic/v1",
            )
            self.assertEqual(diagnostic["classification"], "unavailable")
            self.assertEqual(diagnostic["effect_state"], "unknown")
            self.assertEqual(diagnostic["last_proven_phase"], "staged")
            self.assertEqual(diagnostic["operation_id"], operation)
            self.assertEqual(diagnostic["journal_locator"], locator)
            self.assertEqual(
                diagnostic["next_action"],
                [
                    "acquire",
                    "recover",
                    "inspect",
                    "--xdg-state-home",
                    "<absolute-xdg-state-home>",
                    "--journal-locator",
                    "<journal-locator>",
                ],
            )
            self.assertNotIn(b"credential-canary", errors.getvalue())
            self.assertEqual(journal_path.read_bytes(), journal_before)
            self.assertEqual(self._snapshot(case), before)
            self.assertFalse(
                (
                    case
                    / "state"
                    / "agentic-sdlc"
                    / "acquisition"
                    / "receipts"
                    / f"{archive_sha}.json"
                ).exists()
            )
            self.assertFalse(
                (
                    case
                    / "data"
                    / "agentic-sdlc"
                    / "acquisition"
                    / "candidates"
                    / archive_sha
                ).exists()
            )

    # `_identity` witnesses a same-inode same-length in-place write ONLY through its
    # mtime/ctime terms, so on a host whose filesystem timestamp granularity is coarser
    # than the write window it witnesses nothing at all. Nothing in this test measures any
    # host's granularity and no claim about one is made: quantizing those terms away is a
    # deliberate WORST CASE, and expressing it as a mock is what makes the assertions below
    # granularity-independent on every host, including this one. Every refusal must come
    # from a check that reads no clock, and every acceptance must be an acceptance that
    # removing the clock cannot manufacture.
    @staticmethod
    def _timestamp_free_identity(item: os.stat_result) -> tuple[int, int, int]:
        return item.st_dev, item.st_ino, item.st_size

    @staticmethod
    def _same_length_other_bytes(raw: bytes) -> bytes:
        """Different content, identical length, derived from whatever was admitted."""
        return bytes(byte ^ 0xFF for byte in raw)

    def _apply_over_real_staging_copy(
        self,
        engine,
        case: Path,
        attack,
        *,
        real_identity: bool = False,
    ) -> SimpleNamespace:
        """Drive `apply_hardened` through the production copy-and-verify seam.

        The rest of `_stage_candidate` (a clean-source snapshot, gzip inflation, tar
        admission, manual extraction) is what this class deliberately stands in for, but
        `_copy_fd_at` is the ONE place the pinned archive descriptor is read a second time
        after the last recheck, and those re-read bytes are the ones written to the stage
        and then published, so the real `_stage_candidate` is entered here and runs up to
        its first post-copy step. `attack` races the copy at `data-after-journal`, the
        checkpoint immediately before the stage directory is created.
        """
        arguments, _operation, archive_sha = self._records(case)
        archive = Path(
            json.loads(arguments.plan.read_bytes())["archive_absolute_path"]
        )
        admitted = archive.read_bytes()
        self.assertEqual(hashlib.sha256(admitted).hexdigest(), archive_sha)
        codes: list[str] = []
        real_fail = engine._fail

        def recording_fail(code: str, exit_code: int = 3, **evidence: object) -> None:
            # The exit-4 diagnostic record carries no failure code by design, so the named
            # refusal is captured here instead of being inferred from the exit code alone.
            codes.append(code)
            real_fail(code, exit_code, **evidence)

        real_open_dir_at = engine._open_dir_at
        real_stage_candidate = engine._stage_candidate

        def stop_after_copy(parent_fd, name, display_path, **keywords):
            if name == ".admission":
                raise _StopAfterStagedCopy
            return real_open_dir_at(parent_fd, name, display_path, **keywords)

        def staging(stage, archive_fd, archive_item, plan, candidate, source_root):
            # PRODUCTION must supply the digest the guard compares against, never this
            # harness: a wiring regression that keeps the keyword-only argument but sources
            # it from a live re-read of the mutable archive path is tautological, and a
            # harness that hands the value over itself is structurally unable to see that.
            # So enter the real `_stage_candidate` and stop it at its first step after the
            # copy — opening the private `.admission` scratch directory — then stand in only
            # for the inflation, admission and extraction this class does not perform.
            with mock.patch.object(engine, "_open_dir_at", stop_after_copy):
                try:
                    real_stage_candidate(
                        stage, archive_fd, archive_item, plan, candidate, source_root
                    )
                except _StopAfterStagedCopy:
                    pass
            return self._fake_stage(
                stage, archive_fd, archive_item, plan, candidate, source_root
            )

        def race(point: str) -> None:
            if point == "data-after-journal":
                attack(archive)

        out = io.BytesIO()
        errors = io.BytesIO()
        stdout = SimpleNamespace(
            buffer=out, write=lambda text: out.write(text.encode("utf-8"))
        )
        stderr = SimpleNamespace(
            buffer=errors, write=lambda text: errors.write(text.encode("utf-8"))
        )
        trust = ROOT / "policy" / "release-candidate.v1.json"
        with (
            mock.patch.object(
                engine,
                "_identity",
                engine._identity if real_identity else self._timestamp_free_identity,
            ),
            mock.patch.object(engine, "_fail", recording_fail),
            mock.patch.object(
                engine,
                "_trust_root",
                return_value=(
                    trust,
                    hashlib.sha256(trust.read_bytes()).hexdigest(),
                ),
            ),
            mock.patch.object(engine, "_stage_candidate", side_effect=staging),
            mock.patch.object(engine, "_TEST_RACE_HOOK", race),
            mock.patch.object(engine.sys, "stdout", stdout),
            mock.patch.object(engine.sys, "stderr", stderr),
        ):
            result = engine.apply_hardened(
                arguments,
                self.candidate,
                self.policy,
                self.validator,
                self.source_root,
            )
        return SimpleNamespace(
            result=result,
            codes=codes,
            archive_sha=archive_sha,
            admitted=admitted,
            stdout=out.getvalue(),
            stderr=errors.getvalue(),
        )

    @staticmethod
    def _published(case: Path, archive_sha: str) -> Path:
        return (
            case
            / "data"
            / "agentic-sdlc"
            / "acquisition"
            / "candidates"
            / archive_sha
            / "candidate.tar.gz"
        )

    @staticmethod
    def _receipt(case: Path, archive_sha: str) -> Path:
        return (
            case
            / "state"
            / "agentic-sdlc"
            / "acquisition"
            / "receipts"
            / f"{archive_sha}.json"
        )

    def test_archive_content_recheck_refuses_a_same_inode_mutation_with_no_timestamp_signal(
        self,
    ) -> None:
        def mutate_same_inode(archive: Path) -> None:
            tampered = self._same_length_other_bytes(archive.read_bytes())
            fd = os.open(archive, os.O_WRONLY)
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, tampered)
                os.fsync(fd)
            finally:
                os.close(fd)
            self.assertEqual(archive.read_bytes(), tampered)

        # Control: dropping the timestamp terms must not by itself refuse an untouched
        # archive, so the refusal below is the attack rather than the mock, and the copy
        # this method performs for real must accept the admitted bytes.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            run = self._apply_over_real_staging_copy(
                self.engine, case, lambda _archive: None
            )
            self.assertEqual((run.result, run.codes, run.stderr), (0, [], b""))
            self.assertIn(
                f"archive-sha256={run.archive_sha}".encode("ascii"), run.stdout
            )
            self.assertIn(b"effect-state=complete", run.stdout)
            self.assertEqual(
                self._published(case, run.archive_sha).read_bytes(), run.admitted
            )

        # The attack: dev, ino and size all stay equal across it, so only a content
        # comparison can witness it. Without one this reached exit 0, published the
        # substituted bytes under the admitted digest, and sealed an immutable receipt
        # asserting that digest — an accepted verdict over bytes nobody authorized.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            run = self._apply_over_real_staging_copy(
                self.engine, case, mutate_same_inode
            )
            self.assertEqual(run.result, 4)
            self.assertEqual(run.codes, ["archive-mutated"])
            self.assertEqual(run.stdout, b"")
            diagnostic = json.loads(run.stderr)
            self.assertEqual(diagnostic["effect_state"], "unknown")
            self.assertEqual(diagnostic["last_proven_phase"], "opened")
            self.assertFalse(self._published(case, run.archive_sha).exists())
            self.assertFalse(self._receipt(case, run.archive_sha).exists())

        # The same attack on a host that does record the write is refused for the same
        # reason and by the same code, so the two hosts are not two behaviours.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            run = self._apply_over_real_staging_copy(
                self.engine, case, mutate_same_inode, real_identity=True
            )
            self.assertEqual(run.result, 4)
            self.assertEqual(run.codes, ["archive-mutated"])
            self.assertFalse(self._published(case, run.archive_sha).exists())
            self.assertFalse(self._receipt(case, run.archive_sha).exists())

        # Positive control: the guard, not the harness, is what refuses. Neutralizing the
        # content comparison in a scratch copy of the engine must let the same attack reach
        # a complete, receipted, tampered install. A comparison whose text has moved fails
        # the assertion below loudly rather than degrading into a silent no-op replacement.
        guard = "if digest.hexdigest() != expected_sha256:"
        source = ENGINE_PATH.read_text(encoding="utf-8")
        self.assertIn(guard, source)
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            scratch = case / "release_candidate_acquisition_without_the_guard.py"
            scratch.write_text(
                source.replace(guard, "if False:  # guard neutralized"),
                encoding="utf-8",
            )
            neutralized = load_module(
                "release_candidate_acquisition_neutralized_under_test", scratch
            )
            run = self._apply_over_real_staging_copy(
                neutralized, case, mutate_same_inode
            )
            self.assertEqual((run.result, run.codes, run.stderr), (0, [], b""))
            published = self._published(case, run.archive_sha).read_bytes()
            self.assertEqual(
                published, self._same_length_other_bytes(run.admitted)
            )
            self.assertNotEqual(
                hashlib.sha256(published).hexdigest(), run.archive_sha
            )
            self.assertTrue(self._receipt(case, run.archive_sha).exists())

    def test_archive_path_substitution_is_timestamp_free_before_and_inert_after(
        self,
    ) -> None:
        def substitute(archive: Path) -> None:
            # Equal length on purpose: only the dev/ino terms may witness this.
            replacement = self._same_length_other_bytes(archive.read_bytes())
            archive.rename(archive.with_name("held-archive.tar.gz"))
            archive.write_bytes(replacement)
            archive.chmod(0o600)

        # Before the last recheck, a substitution is caught by the dev/ino half of
        # `_identity`, which needs no clock: the refusal survives the timestamp terms being
        # mocked away, and it lands at exit 2 before any target effect.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            arguments, _operation, _archive_sha = self._records(case)
            fired = False

            def archive_race(point: str, path: Path, _fd: int) -> None:
                nonlocal fired
                if point == "external-after-open:archive-path" and not fired:
                    fired = True
                    substitute(path)

            trust = ROOT / "policy" / "release-candidate.v1.json"
            with (
                mock.patch.object(
                    self.engine, "_identity", self._timestamp_free_identity
                ),
                mock.patch.object(
                    self.engine, "_TEST_EXTERNAL_RACE_HOOK", archive_race
                ),
                mock.patch.object(
                    self.engine,
                    "_trust_root",
                    return_value=(
                        trust,
                        hashlib.sha256(trust.read_bytes()).hexdigest(),
                    ),
                ),
            ):
                with self.assertRaises(self.engine.AcquisitionFailure) as raised:
                    self.engine.apply_hardened(
                        arguments,
                        self.candidate,
                        self.policy,
                        self.validator,
                        self.source_root,
                    )
            self.assertTrue(fired)
            self.assertEqual(raised.exception.code, "archive-path-race")
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertFalse((case / "state" / "agentic-sdlc").exists())
            self.assertFalse((case / "data" / "agentic-sdlc").exists())

        # After the last recheck the substitution is inert rather than refused, and that is
        # the load-bearing difference from `release_candidate.py::_pin_archive`, which must
        # re-resolve its admitted path because its own output IS that path's digest. Here
        # the descriptor holds the admitted inode, so the copy consumes the admitted bytes
        # and the substituted name never reaches the stage. Asserting the acceptance keeps
        # the fd-custody property from silently regressing into a path re-open.
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            run = self._apply_over_real_staging_copy(self.engine, case, substitute)
            self.assertEqual((run.result, run.codes, run.stderr), (0, [], b""))
            self.assertIn(b"effect-state=complete", run.stdout)
            published = self._published(case, run.archive_sha).read_bytes()
            self.assertEqual(published, run.admitted)
            self.assertEqual(
                hashlib.sha256(published).hexdigest(), run.archive_sha
            )


@unittest.skipUnless(
    sys.platform == "linux" and os.uname().machine in {"x86_64", "amd64"},
    "genuine acquisition needs Linux x64",
)
class AcquisitionGenuineEndToEndTests(unittest.TestCase):
    def test_genuine_archive_staged_recovery_private_subprocess_and_outer_readback(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            case = Path(raw)
            phases: list[str] = []
            # The clone has an independent, explicit lifetime. It is not owned by
            # the lifecycle/output temporary context and is removed only by the
            # unittest cleanup stack after the entire genuine canary returns.
            source_owner = Path(
                tempfile.mkdtemp(prefix=".acquisition-source-", dir=ROOT)
            )
            self.addCleanup(shutil.rmtree, source_owner, True)
            repository = source_owner / "repository"
            cloned = subprocess.run(
                ["/usr/bin/git", "clone", "-q", "--no-hardlinks", str(ROOT), str(repository)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(cloned.returncode, 0, cloned.stderr)
            self.assertFalse(repository.is_relative_to(case))
            phases.append("clean-clone")
            for relative in (
                "policy/release-candidate-acquisition.v1.json",
                "scripts/validate_bundle.py",
                "scripts/release_candidate.py",
                "scripts/release_candidate_acquisition.py",
            ):
                destination = repository / relative
                shutil.copy2(ROOT / relative, destination)
            staged = subprocess.run(
                ["/usr/bin/git", "-C", str(repository), "add", "policy/release-candidate-acquisition.v1.json", "scripts/validate_bundle.py", "scripts/release_candidate.py", "scripts/release_candidate_acquisition.py"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(staged.returncode, 0, staged.stderr)
            changed = subprocess.run(
                ["/usr/bin/git", "-C", str(repository), "diff", "--cached", "--quiet"],
                capture_output=True, text=True, check=False,
            )
            self.assertIn(changed.returncode, {0, 1}, changed.stderr)
            if changed.returncode == 1:
                committed = subprocess.run(
                    ["/usr/bin/git", "-C", str(repository), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "genuine acquisition test"],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(committed.returncode, 0, committed.stderr)
            status = subprocess.run(
                ["/usr/bin/git", "-C", str(repository), "status", "--porcelain"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(status.stdout, "")
            phases.append("current-clean-source")

            repository_fd = os.open(
                repository,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            )
            git_fd = os.open(
                repository / ".git",
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            )
            self.addCleanup(os.close, repository_fd)
            self.addCleanup(os.close, git_fd)
            repository_identity = (
                os.fstat(repository_fd).st_dev,
                os.fstat(repository_fd).st_ino,
            )
            git_identity = (os.fstat(git_fd).st_dev, os.fstat(git_fd).st_ino)

            def source_evidence(snapshot=None) -> tuple[str, str, str]:
                self.assertTrue(repository.is_dir())
                self.assertTrue((repository / ".git").is_dir())
                routed_repository = repository.lstat()
                routed_git = (repository / ".git").lstat()
                self.assertEqual(
                    (routed_repository.st_dev, routed_repository.st_ino),
                    repository_identity,
                )
                self.assertEqual(
                    (routed_git.st_dev, routed_git.st_ino), git_identity
                )
                values: list[str] = []
                for revision in ("HEAD^{commit}", "HEAD^{tree}"):
                    completed = subprocess.run(
                        [
                            "/usr/bin/git",
                            "-C",
                            str(repository),
                            "rev-parse",
                            "--verify",
                            revision,
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    values.append(completed.stdout.strip())
                clean = subprocess.run(
                    ["/usr/bin/git", "-C", str(repository), "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(clean.returncode, 0, clean.stderr)
                self.assertEqual(clean.stdout, "")
                if snapshot is not None:
                    self.assertEqual(snapshot.root, repository)
                    self.assertEqual(values, [snapshot.commit, snapshot.tree])
                return values[0], values[1], clean.stdout

            candidate = load_module(
                "release_candidate_genuine_acquisition_under_test",
                repository / "scripts" / "release_candidate.py",
            )
            engine = load_module(
                "release_candidate_acquisition_genuine_under_test",
                repository / "scripts" / "release_candidate_acquisition.py",
            )
            policy, runtime_validator, source_root = engine._load_policy(candidate)
            self.assertEqual(source_root, repository)
            # Everything below runs the REAL `_stage_candidate`, so this is where the
            # digest the staging copy is checked against can be observed as production
            # supplies it. Presence of the keyword-only argument is not the property worth
            # locking — a wiring change that keeps it but hands over some other digest
            # would still be a regression, so record the VALUE of every one received.
            staged_expectations: list[str] = []
            real_copy_fd_at = engine._copy_fd_at

            def recording_copy_fd_at(
                source_fd, expected, destination, name, *, expected_sha256
            ):
                staged_expectations.append(expected_sha256)
                real_copy_fd_at(
                    source_fd,
                    expected,
                    destination,
                    name,
                    expected_sha256=expected_sha256,
                )

            copy_spy = mock.patch.object(
                engine, "_copy_fd_at", recording_copy_fd_at
            )
            copy_spy.start()
            self.addCleanup(copy_spy.stop)
            admitted_source = candidate.admit_source(repository)
            output_dir = case / "output"; output_dir.mkdir(mode=0o700)
            before_build = source_evidence(admitted_source)
            archive = candidate.build_candidate(
                output_dir, snapshot=admitted_source
            )
            self.assertEqual(source_evidence(admitted_source), before_build)
            self.assertTrue(archive.is_file())
            phases.append("real-build")
            data = case / "data"; state = case / "state"
            data.mkdir(mode=0o700); state.mkdir(mode=0o700)
            poison = case / "poison"; poison.mkdir(mode=0o700)
            marker = case / "ambient-tool-ran"
            for name in ("python", "python3", "uv", "mise", "git", "curl"):
                tool = poison / name
                tool.write_text(f"#!/bin/sh\nprintf x >> '{marker}'\nexit 91\n")
                tool.chmod(0o755)
            poisoned = {
                "HOME": str(case / "poison-home"),
                "XDG_DATA_HOME": str(case / "poison-data"),
                "XDG_STATE_HOME": str(case / "poison-state"),
                "TMPDIR": str(case / "poison-tmp"),
                "PATH": str(poison),
                "PYTHONPATH": str(case / "poison-python"),
                "PYTHONHOME": str(case / "poison-python-home"),
                "UV_CACHE_DIR": str(case / "poison-uv"),
                "MISE_CONFIG_ROOT": str(case / "poison-mise"),
                "HTTPS_PROXY": "http://credential-canary.invalid/path",
                "ALL_PROXY": "http://credential-canary.invalid/path",
                "ANTHROPIC_API_KEY": "credential-canary",
            }
            stdout_bytes = io.BytesIO(); stderr_bytes = io.BytesIO()
            stdout = SimpleNamespace(buffer=stdout_bytes, write=lambda text: stdout_bytes.write(text.encode("utf-8")))
            stderr = SimpleNamespace(buffer=stderr_bytes, write=lambda text: stderr_bytes.write(text.encode("utf-8")))
            plan_args = SimpleNamespace(
                archive=archive,
                trust_root=repository / "policy" / "release-candidate.v1.json",
                xdg_data_home=data,
                xdg_state_home=state,
            )
            with mock.patch.dict(os.environ, poisoned, clear=False), mock.patch.object(engine.sys, "stdout", stdout), mock.patch.object(engine.sys, "stderr", stderr):
                self.assertEqual(engine.plan(plan_args, candidate, policy, runtime_validator, source_root), 0)
            phases.append("explicit-plan")
            plan_raw = stdout_bytes.getvalue(); plan = json.loads(plan_raw)
            plan_path = case / "plan.json"; plan_path.write_bytes(plan_raw); plan_path.chmod(0o600)

            def mint(decision: str, nonce: str, journal_path: Path | None = None) -> Path:
                now = datetime.now(timezone.utc).replace(microsecond=0)
                grant = {
                    "archive_absolute_path": plan["archive_absolute_path"], "archive_sha256": plan["archive_sha256"],
                    "archive_size_bytes": plan["archive_size_bytes"], "decision": decision,
                    "effects_sha256": plan["effects_sha256"],
                    "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "issued_at": (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "nonce": nonce, "operation_id": "op-fedcba9876543210fedcba9876543210",
                    "original_effects": list(engine.EFFECTS),
                    "plan_sha256": hashlib.sha256(plan_raw).hexdigest(), "record_sha256": "",
                    "same_user_uid": os.geteuid(),
                    "schema_version": f"release-candidate-acquisition-{'apply' if decision == 'apply' else 'recover-finish'}-grant/v1",
                    "trust_root_absolute_path": plan["trust_root_absolute_path"], "trust_root_sha256": plan["trust_root_sha256"],
                    "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"], "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
                    "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"], "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
                }
                if journal_path is not None:
                    grant["journal_absolute_physical_path"] = str(journal_path)
                    grant["journal_sha256"] = hashlib.sha256(journal_path.read_bytes()).hexdigest()
                path = case / f"{decision}-grant.json"
                path.write_bytes(record_bytes(grant)); path.chmod(0o600)
                return path

            apply_grant = mint("apply", "e" * 64)
            apply_args = SimpleNamespace(plan=plan_path, grant=apply_grant)
            stdout_bytes.seek(0); stdout_bytes.truncate(); stderr_bytes.seek(0); stderr_bytes.truncate()
            def staged_fault(phase: str) -> None:
                if phase == "staged": raise RuntimeError("genuine staged crash")
            with (
                mock.patch.dict(os.environ, poisoned, clear=False),
                mock.patch.object(engine, "_TEST_FAULT_HOOK", staged_fault),
                mock.patch.object(engine.sys, "stdout", stdout),
                mock.patch.object(engine.sys, "stderr", stderr),
            ):
                self.assertEqual(engine.apply_hardened(apply_args, candidate, policy, runtime_validator, source_root), 4)
            diagnostic = json.loads(stderr_bytes.getvalue())
            self.assertEqual(diagnostic["last_proven_phase"], "staged")
            staged_root = data / "agentic-sdlc" / "acquisition" / "staging" / "op-fedcba9876543210fedcba9876543210" / "root"
            self.assertTrue((staged_root / "manifest.json").is_file())
            self.assertTrue((staged_root / "runtime" / "python" / "bin" / "python3.12").is_file())
            phases.append("real-admission-extraction-staged")
            locator = diagnostic["journal_locator"]
            journal_path = state / "agentic-sdlc" / "acquisition" / "journals" / "op-fedcba9876543210fedcba9876543210.json"
            recovery_grant = mint("finish", "f" * 64, journal_path)
            finish_args = SimpleNamespace(
                xdg_state_home=state,
                journal_locator=locator,
                grant=recovery_grant,
            )
            stdout_bytes.seek(0); stdout_bytes.truncate(); stderr_bytes.seek(0); stderr_bytes.truncate()
            real_subprocess_run = engine.subprocess.run
            private_invocations: list[list[str]] = []
            def track_private(*args, **kwargs):
                argv = list(args[0])
                if "-I" in argv and "-B" in argv and "recover" in argv:
                    private_invocations.append(argv)
                return real_subprocess_run(*args, **kwargs)
            with mock.patch.dict(os.environ, poisoned, clear=False), mock.patch.object(engine.subprocess, "run", side_effect=track_private), mock.patch.object(engine.sys, "stdout", stdout), mock.patch.object(engine.sys, "stderr", stderr):
                self.assertEqual(engine.recover_finish_hardened(finish_args, candidate, policy, runtime_validator, source_root), 0)
            self.assertEqual(len(private_invocations), 1)
            self.assertEqual(private_invocations[0][1:3], ["-I", "-B"])
            phases.append("real-private-subprocess")
            terminal = json.loads(stdout_bytes.getvalue())
            self.assertEqual(terminal["last_proven_phase"], "installed-unselected")
            phases.append("outer-terminal-readback")

            before = AcquisitionEngineLifecycleTests._snapshot(case)
            stdout_bytes.seek(0); stdout_bytes.truncate(); stderr_bytes.seek(0); stderr_bytes.truncate()
            with mock.patch.dict(os.environ, poisoned, clear=False), mock.patch.object(engine.sys, "stdout", stdout), mock.patch.object(engine.sys, "stderr", stderr):
                self.assertEqual(engine.inspect(SimpleNamespace(plan=plan_path), candidate, policy, runtime_validator, source_root), 0)
                self.assertEqual(engine.apply_hardened(apply_args, candidate, policy, runtime_validator, source_root), 0)
            self.assertEqual(AcquisitionEngineLifecycleTests._snapshot(case), before)
            phases.append("inspect-exact-rerun")
            final_archive = data / "agentic-sdlc" / "acquisition" / "candidates" / plan["archive_sha256"] / "candidate.tar.gz"
            final_archive.write_bytes(b"tampered\n")
            with self.assertRaises(engine.AcquisitionFailure) as raised:
                engine.inspect(SimpleNamespace(plan=plan_path), candidate, policy, runtime_validator, source_root)
            self.assertEqual(raised.exception.exit_code, 3)
            phases.append("tamper-refusal")
            # One real staging copy happened in this canary — the crashed apply's — and the
            # recovery from `staged` re-publishes the already-staged tree rather than copying
            # again, so the exact list locks the value AND proves the spy was not vacuous.
            self.assertEqual(staged_expectations, [plan["archive_sha256"]])
            self.assertFalse(marker.exists())
            for path in ("poison-home", "poison-data", "poison-state", "poison-tmp", "poison-python-home", "poison-uv", "poison-mise"):
                self.assertFalse((case / path).exists())
            self.assertEqual(
                phases,
                [
                    "clean-clone",
                    "current-clean-source",
                    "real-build",
                    "explicit-plan",
                    "real-admission-extraction-staged",
                    "real-private-subprocess",
                    "outer-terminal-readback",
                    "inspect-exact-rerun",
                    "tamper-refusal",
                ],
            )
            self.assertEqual(source_evidence(admitted_source), before_build)


ENGINE_PATH = ROOT / "scripts" / "release_candidate_acquisition.py"

# Every diagnostic-bearing exit this family declares, plus the codes that must stay unreachable
# on the diagnostic path: CPython's 120 (a shutdown flush of a broken stderr) above all.
DECLARED_ACQUISITION_EXITS = frozenset({0, 1, 2, 3, 4})


def _injected_failures(engine) -> dict[str, tuple[object, int]]:
    """One injection per handler arm in `run`, with the exit code each arm must still return."""
    locator = f"journal:v1:op-{'0' * 32}:{'d' * 64}"
    return {
        "exit4": (
            engine.AcquisitionFailure(
                "test-injected", 4, f"op-{'0' * 32}", locator, "published", "exact"
            ),
            4,
        ),
        "exit3": (engine.AcquisitionFailure("test-injected-refusal", 3), 3),
        "internal": (RuntimeError("test-injected internal"), 1),
    }


class AcquisitionRunDiagnosticSinkTests(unittest.TestCase):
    """`run`'s own handlers: a diagnostic channel may cost the display and nothing else.

    `run` is where a diagnostic failure used to be worst: an `AttributeError` from
    `sys.stderr.buffer` inside the exit-4 arm escaped into the dispatcher, and the stable one-line
    arm used `print(..., file=sys.stderr)` — which, with `2>&-` making `sys.stderr` `None`, CPython
    redirects to `sys.stdout`, putting a diagnostic on the wire this family reserves for canonical
    records.  Both are asserted here, per arm.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = load_module("release_candidate_acquisition_sink_under_test", ENGINE_PATH)

    def _run(self, *, sink: object, failure: object) -> tuple[int, io.BytesIO]:
        """Drive `run` with one injected failure and one stderr shape. Returns (code, stdout bytes).

        `_load_policy` and `plan` are the only injections: the sink under test lives in `run`'s own
        handlers, so no lifecycle fixture is needed to reach it, and none is used — a fixture failing
        for its own reasons is exactly the trap these assertions must not fall into.
        """
        captured = io.BytesIO()
        stdout = SimpleNamespace(
            buffer=captured, write=lambda text: captured.write(text.encode("utf-8"))
        )
        with (
            mock.patch.object(
                self.engine, "_load_policy", return_value=({}, None, Path("/nonexistent"))
            ),
            mock.patch.object(self.engine, "plan", side_effect=failure),
            mock.patch.object(self.engine.sys, "stdout", stdout),
            mock.patch.object(self.engine.sys, "stderr", sink),
        ):
            code = self.engine.run(SimpleNamespace(acquire_action="plan"), candidate=None)
        return code, captured

    def _expected_reason(self, arm: str, failure: object) -> bytes:
        if arm == "exit4":
            return self.engine._diagnostic(failure)
        if arm == "exit3":
            return b"release-candidate-acquisition: test-injected-refusal\n"
        return b"release-candidate-acquisition: internal\n"

    def test_a_text_stderr_keeps_every_arms_exit_code_and_its_reason(self) -> None:
        for arm, (failure, expected) in _injected_failures(self.engine).items():
            with self.subTest(arm=arm):
                text = io.StringIO()
                code, stdout = self._run(sink=text, failure=failure)
                self.assertEqual(code, expected)  # the AttributeError used to make this 1
                self.assertIn(code, DECLARED_ACQUISITION_EXITS)
                self.assertEqual(
                    text.getvalue().encode("utf-8"), self._expected_reason(arm, failure)
                )
                self.assertEqual(stdout.getvalue(), b"")  # diagnostics never touch the wire
                # POSITIVE CONTROL: the byte-stderr shape produces byte-identical output for the
                # same arm, so the comparison above is against a live channel.
                errors = io.BytesIO()
                stderr = SimpleNamespace(
                    buffer=errors, write=lambda t: errors.write(t.encode("utf-8"))
                )
                control_code, control_stdout = self._run(sink=stderr, failure=failure)
                self.assertEqual(control_code, expected)
                self.assertEqual(errors.getvalue(), text.getvalue().encode("utf-8"))
                self.assertEqual(control_stdout.getvalue(), b"")

    def test_a_closed_fd_2_costs_the_reason_and_never_the_exit_code_or_the_wire(self) -> None:
        """`2>&-` in-process is `sys.stderr is None`, which is how CPython itself represents it."""
        for arm, (failure, expected) in _injected_failures(self.engine).items():
            with self.subTest(arm=arm):
                code, stdout = self._run(sink=None, failure=failure)
                self.assertEqual(code, expected)
                self.assertIn(code, DECLARED_ACQUISITION_EXITS)
                # The stable one-line arms went through `print(..., file=sys.stderr)`, and `print`
                # treats a `None` file as `sys.stdout`: this is the assertion that catches it.
                self.assertEqual(stdout.getvalue(), b"")
        # POSITIVE CONTROL: with a usable stderr the same arms DO deliver their reason, so the
        # emptiness asserted above is the missing stream and not a silent engine.
        for arm, (failure, expected) in _injected_failures(self.engine).items():
            errors = io.BytesIO()
            stderr = SimpleNamespace(buffer=errors, write=lambda t: errors.write(t.encode("utf-8")))
            code, stdout = self._run(sink=stderr, failure=failure)
            self.assertEqual(code, expected)
            self.assertEqual(errors.getvalue(), self._expected_reason(arm, failure))
            self.assertEqual(stdout.getvalue(), b"")

    def test_a_failing_write_retires_the_channel_and_drops_the_stream(self) -> None:
        """EPIPE mid-write: the code survives, and the stream is dropped so 120 cannot replace it."""
        for arm, (failure, expected) in _injected_failures(self.engine).items():
            with self.subTest(arm=arm):
                broken = SimpleNamespace(
                    buffer=mock.Mock(**{"write.side_effect": OSError(errno.EPIPE, "broken pipe")}),
                    write=lambda text: None,
                )
                original = sys.stderr
                try:
                    code, stdout = self._run(sink=broken, failure=failure)
                finally:
                    sys.stderr = original
                # POSITIVE CONTROL on the injection: the sink was REACHED and it DID fail.
                self.assertTrue(broken.buffer.write.called)
                self.assertEqual(code, expected)
                self.assertEqual(stdout.getvalue(), b"")

    def test_the_settled_sink_writes_where_it_can_and_never_raises_where_it_cannot(self) -> None:
        """The primitive itself, across every stream shape an importable entrypoint may be handed."""
        payload = b"diagnostic-bytes\n"
        text = io.StringIO()
        with mock.patch.object(sys, "stderr", text):
            self.engine._diagnostic_sink()(payload)
        self.assertEqual(text.getvalue(), payload.decode("utf-8"))
        raw = io.BytesIO()
        with mock.patch.object(
            sys, "stderr", SimpleNamespace(buffer=raw, write=lambda t: None)
        ):
            self.engine._diagnostic_sink()(payload)
        self.assertEqual(raw.getvalue(), payload)
        # A `write` with no `flush` is a shape a caller may hand an entrypoint, and it must not
        # become a new way to lose the reason.
        flushless: list[str] = []
        with mock.patch.object(
            sys, "stderr", SimpleNamespace(write=lambda t: flushless.append(t))
        ):
            self.engine._diagnostic_sink()(payload)
        self.assertEqual(flushless, [payload.decode("utf-8")])
        with mock.patch.object(sys, "stderr", None):
            self.engine._diagnostic_sink()(payload)  # nowhere to write, and not a failure
            self.assertIsNone(sys.stderr)

    def test_a_stream_whose_shape_cannot_even_be_resolved_costs_only_the_channel(self) -> None:
        """The narrowest shape, and the one that would put the reporter back inside a `try`.

        `getattr(stream, "buffer", ...)` suppresses only `AttributeError`; a `.buffer` that raises
        anything else would otherwise escape the sink's own construction, which happens outside every
        handler — so the resolution is settled defensively and the arm keeps its exit code.
        """

        class _UnresolvableStderr:
            @property
            def buffer(self) -> object:
                raise RuntimeError("this stream cannot describe itself")

            def write(self, text: str) -> int:
                raise AssertionError("a stream that cannot be resolved must never be written to")

        hostile = _UnresolvableStderr()
        with mock.patch.object(sys, "stderr", hostile):
            self.engine._diagnostic_sink()(b"nowhere\n")  # neither raises nor writes
        for arm, (failure, expected) in _injected_failures(self.engine).items():
            with self.subTest(arm=arm):
                code, stdout = self._run(sink=hostile, failure=failure)
                self.assertEqual(code, expected)
                self.assertEqual(stdout.getvalue(), b"")
        # POSITIVE CONTROL: the resolution is not simply always giving up — a resolvable stream on
        # the same code path still receives the reason.
        errors = io.BytesIO()
        with mock.patch.object(
            sys, "stderr", SimpleNamespace(buffer=errors, write=lambda t: None)
        ):
            self.engine._diagnostic_sink()(b"nowhere\n")
        self.assertEqual(errors.getvalue(), b"nowhere\n")

    def test_only_the_stream_that_failed_is_ever_dropped(self) -> None:
        """These entrypoints are importable, so the caller may have swapped the stream since."""
        settled = SimpleNamespace(
            buffer=mock.Mock(**{"write.side_effect": OSError(errno.EPIPE, "broken pipe")}),
            write=lambda text: None,
        )
        replacement = io.StringIO()
        with mock.patch.object(sys, "stderr", settled):
            report = self.engine._diagnostic_sink()
            sys.stderr = replacement  # a caller swaps it after the sink settled
            report(b"lost\n")
            self.assertIs(sys.stderr, replacement)  # not ours to drop
        with mock.patch.object(sys, "stderr", settled):
            self.engine._diagnostic_sink()(b"lost\n")
            self.assertIsNone(sys.stderr)  # this one failed, so it goes
        # POSITIVE CONTROL: the replacement stream is writable, so the first case really could have
        # been written to had the sink wrongly re-resolved it.
        replacement.write("proof\n")
        self.assertEqual(replacement.getvalue(), "proof\n")

    def test_a_retired_channel_is_never_written_to_again(self) -> None:
        stream = SimpleNamespace(
            buffer=mock.Mock(**{"write.side_effect": OSError(errno.EPIPE, "broken pipe")}),
            write=lambda text: None,
        )
        original = sys.stderr
        try:
            with mock.patch.object(sys, "stderr", stream):
                report = self.engine._diagnostic_sink()
                report(b"first\n")  # fails, and retires the channel
                report(b"second\n")  # never attempted
        finally:
            sys.stderr = original
        self.assertEqual(stream.buffer.write.call_count, 1)
        self.assertEqual(stream.buffer.write.call_args_list[0].args, (b"first\n",))


def _acquisition_driver(directory: Path) -> Path:
    """A child that reaches ONE `run` handler arm with real file descriptors.

    In-process shapes cover the stream objects; only a real child can carry a real `2>&-` and a real
    broken pipe, which is where CPython's 120 comes from. The injections are the same two module
    attributes the in-process tests patch, so the arm under test is the engine's own.
    """
    driver = directory / "acquisition_stderr_driver.py"
    driver.write_text(
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        "from types import SimpleNamespace\n"
        "engine_path, arm = Path(sys.argv[1]), sys.argv[2]\n"
        "spec = importlib.util.spec_from_file_location('release_candidate_acquisition', engine_path)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "locator = 'journal:v1:op-' + '0' * 32 + ':' + 'd' * 64\n"
        "failures = {\n"
        "    'exit4': module.AcquisitionFailure(\n"
        "        'test-injected', 4, 'op-' + '0' * 32, locator, 'published', 'exact'\n"
        "    ),\n"
        "    'exit3': module.AcquisitionFailure('test-injected-refusal', 3),\n"
        "    'internal': RuntimeError('test-injected internal'),\n"
        "}\n"
        "def raiser(*args, **kwargs):\n"
        "    raise failures[arm]\n"
        "module._load_policy = lambda candidate: ({}, None, Path('/nonexistent'))\n"
        "module.plan = raiser\n"
        "code = module.run(SimpleNamespace(acquire_action='plan'), candidate=None)\n"
        "sys.stdout.write('code=%d\\n' % code)\n"
        "sys.stdout.flush()\n"
        "sys.exit(code)\n",
        encoding="utf-8",
    )
    return driver


def _run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr the child CANNOT write to. Returns (exit code, stdout bytes).

    Re-expressed from `tests/test_gate_receipt_producer.py`'s harness for the same two shapes, kept
    local so neither test module can break the other:

        closed  `exec 2>&-`, so the interpreter starts with `sys.stderr is None` and the first
                `sys.stderr.buffer` raises `AttributeError` rather than `OSError`.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write
                raises EPIPE AND leaves bytes pending that the interpreter flushes again while
                finalizing — which is what replaces the exit code with 120.

    Stderr is deliberately not captured: capturing it would hand the child a writable stream.
    """
    if mode == "closed":
        proc = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
        )
        return proc.returncode, proc.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd))
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def _stderr_is_really_hostile(mode: str, cwd: Path) -> str:
    """What a canary child OBSERVES about its own stderr, reported over stdout."""
    canary = (
        "import sys\n"
        "if sys.stderr is None:\n"
        "    print('none')\n"
        "else:\n"
        "    try:\n"
        "        sys.stderr.write('x')\n"
        "        sys.stderr.flush()\n"
        "        print('writable')\n"
        "    except OSError as exc:\n"
        "        print(type(exc).__name__)\n"
    )
    code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode=mode, cwd=cwd)
    return f"{code}:{out.decode('utf-8', 'replace').strip()}"


@unittest.skipUnless(os.name == "posix", "fd-level stderr hostility is POSIX-only")
class AcquisitionHostileStderrTests(unittest.TestCase):
    """With REAL file descriptors: 120 must be unreachable, not merely unlikely."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.driver = _acquisition_driver(self.tmp)

    def test_the_hostile_stderr_fixture_is_actually_hostile(self) -> None:
        """The control for every negative assertion below.

        The canary's own exit codes are the second half of it: under a broken pipe the canary
        CATCHES its `BrokenPipeError` and still exits 120, because the bytes it left pending are
        flushed again during finalization — which is why swallowing the write is not enough on its
        own, and why the sink also stops claiming the stream.
        """
        self.assertEqual(_stderr_is_really_hostile("closed", self.tmp), "0:none")
        self.assertEqual(_stderr_is_really_hostile("epipe", self.tmp), "120:BrokenPipeError")

    def test_no_hostile_stderr_can_change_an_arms_exit_code(self) -> None:
        for mode in ("closed", "epipe"):
            for arm, expected in (("exit4", 4), ("exit3", 3), ("internal", 1)):
                with self.subTest(mode=mode, arm=arm):
                    code, stdout = _run_with_hostile_stderr(
                        [sys.executable, "-B", str(self.driver), str(ENGINE_PATH), arm],
                        mode=mode,
                        cwd=self.tmp,
                    )
                    # The engine's own decision, carried out over stdout, versus what the shell saw:
                    # 120 is exactly the case where those two disagree.
                    self.assertEqual(stdout, f"code={expected}\n".encode("utf-8"))
                    self.assertEqual(code, expected)
                    self.assertIn(code, DECLARED_ACQUISITION_EXITS)
                    self.assertNotEqual(code, 120)

    def test_the_same_arms_over_a_working_stderr_do_report_their_reason(self) -> None:
        """POSITIVE CONTROL for the whole class: the driver reaches the site and it does write."""
        expectations = {
            "exit4": b'"schema_version":"release-candidate-acquisition-exit4-diagnostic/v1"',
            "exit3": b"release-candidate-acquisition: test-injected-refusal\n",
            "internal": b"release-candidate-acquisition: internal\n",
        }
        for arm, expected_reason in expectations.items():
            with self.subTest(arm=arm):
                proc = subprocess.run(
                    [sys.executable, "-B", str(self.driver), str(ENGINE_PATH), arm],
                    capture_output=True,
                    cwd=str(self.tmp),
                    check=False,
                )
                self.assertIn(expected_reason, proc.stderr)
                self.assertEqual(proc.stdout, b"code=%d\n" % proc.returncode)
                self.assertNotEqual(proc.returncode, 120)


if __name__ == "__main__":
    unittest.main()
