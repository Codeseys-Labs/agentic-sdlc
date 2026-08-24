"""Release-contract policy conformance tests."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path


ROOT = Path(__file__).parents[1]
BUNDLE_VALIDATOR = ROOT / "scripts" / "validate_bundle.py"
POLICY_PATH = ROOT / "policy" / "release-contract.v1.json"
FIXTURES = ROOT / "tests" / "fixtures" / "release-contract"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bundle_validator = load_module("bundle_validator_release_contract", BUNDLE_VALIDATOR)


def load_contract_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def validate_contract(
    contract: dict[str, object],
    claims: dict[str, str] | None = None,
    outside: str | None = None,
    fixture_setup: Callable[[Path, Path], None] | None = None,
) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = root / "policy"
        fixture_root = root / "tests" / "fixtures" / "release-claims"
        policy.mkdir()
        fixture_root.parent.mkdir(parents=True)
        (policy / "release-contract.v1.json").write_text(
            bundle_validator.canonical_release_contract_json(contract), encoding="utf-8"
        )
        if fixture_setup is None:
            fixture_root.mkdir()
            (fixture_root / "truthful.md").write_text(
                "The fixture only describes one exact tuple.\n", encoding="utf-8"
            )
        else:
            fixture_setup(root, fixture_root)
        for name, text in (claims or {}).items():
            (fixture_root / name).write_text(text, encoding="utf-8")
        if outside is not None:
            historical = root / "docs" / "historical.md"
            historical.parent.mkdir()
            historical.write_text(outside, encoding="utf-8")
        result = bundle_validator.Validation()
        bundle_validator.validate_release_contract(root, result)
        return result.errors


class ReleaseContractIdentityTests(unittest.TestCase):
    def _validate_raw_contract(self, fixture_name: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "policy"
            policy.mkdir()
            (policy / "release-contract.v1.json").write_bytes(
                (FIXTURES / fixture_name).read_bytes()
            )
            result = bundle_validator.Validation()
            bundle_validator.validate_release_contract(root, result)
            return result.errors

    def test_shipped_contract_is_canonical_checkout_development_policy(self) -> None:
        result = bundle_validator.Validation()
        bundle_validator.validate_release_contract(ROOT, result)
        self.assertEqual(result.errors, [], result.errors)

        contract = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], "release-contract/v1")
        self.assertEqual(contract["checkout"]["version"], "0.7.4")
        self.assertEqual(contract["checkout"]["plane"], "checkout-development")
        self.assertIsNone(contract["checkout"]["public_channel"])
        self.assertEqual(contract["checkout"]["certification_claim"], "none")
        self.assertEqual(
            POLICY_PATH.read_text(encoding="utf-8"),
            bundle_validator.canonical_release_contract_json(contract),
        )

    def test_duplicate_members_are_rejected(self) -> None:
        errors = self._validate_raw_contract("duplicate-member.json")
        self.assertTrue(
            any("duplicate member" in error for error in errors),
            errors,
        )

    def test_nan_is_rejected(self) -> None:
        errors = self._validate_raw_contract("nonfinite-nan.json")
        self.assertTrue(any("non-finite" in error for error in errors), errors)

    def test_infinity_is_rejected(self) -> None:
        errors = self._validate_raw_contract("nonfinite-infinity.json")
        self.assertTrue(any("non-finite" in error for error in errors), errors)


class ReleaseContractCompatibilityTests(unittest.TestCase):
    def _stable_fixture(self) -> dict[str, object]:
        return load_contract_fixture("stable-valid.json")

    @staticmethod
    def _preview(contract: dict[str, object]) -> None:
        checkout = contract["checkout"]
        assert isinstance(checkout, dict)
        checkout["certification_claim"] = "none"
        checkout["public_channel"] = "preview"

    def test_stable_fixture_requires_current_certified_core_tuple(self) -> None:
        stable = self._stable_fixture()
        self.assertEqual(validate_contract(stable), [])

        compatibility = stable["compatibility"]
        assert isinstance(compatibility, dict)
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["tier"] = "capability-qualified"
        errors = validate_contract(stable)
        self.assertTrue(any("stable requires a current certified Core tuple" in error for error in errors), errors)

    def test_below_minimum_core_tuple_is_only_unsupported(self) -> None:
        contract = self._stable_fixture()
        self._preview(contract)
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["host_version"] = "2.1.153"
        rows[0]["tier"] = "capability-qualified"
        errors = validate_contract(contract)
        self.assertTrue(any("below the Core minimum" in error for error in errors), errors)

    def test_minimum_eligibility_alone_never_certifies(self) -> None:
        contract = self._stable_fixture()
        self._preview(contract)
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["host_version"] = "2.1.154"
        evidence = rows[0]["capability_evidence"]
        assert isinstance(evidence, dict)
        evidence["published_journey"] = False
        errors = validate_contract(contract)
        self.assertTrue(any("published journey" in error for error in errors), errors)

    def test_unlisted_newer_core_tuple_can_be_capability_qualified(self) -> None:
        contract = self._stable_fixture()
        self._preview(contract)
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["host_version"] = "2.1.999"
        rows[0]["tier"] = "capability-qualified"
        evidence = rows[0]["capability_evidence"]
        assert isinstance(evidence, dict)
        evidence["published_journey"] = False
        self.assertEqual(validate_contract(contract), [])

    def test_dated_references_cannot_become_certifications_or_ceilings(self) -> None:
        contract = self._stable_fixture()
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        references = compatibility["dated_references"]
        assert isinstance(references, dict)
        stable_reference = references["stable"]
        assert isinstance(stable_reference, dict)
        stable_reference["certification"] = True
        stable_reference["ceiling"] = True
        errors = validate_contract(contract)
        self.assertTrue(any("dated reference" in error for error in errors), errors)

    def test_support_tuple_keeps_dependency_versions_separate(self) -> None:
        contract = self._stable_fixture()
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["dependency_versions"] = {"seeds-cli": "0.5.15"}
        self.assertEqual(validate_contract(contract), [])

        rows[0].pop("dependency_versions")
        errors = validate_contract(contract)
        self.assertTrue(any("dependency_versions" in error for error in errors), errors)

    def test_known_incompatible_host_version_must_be_unsupported(self) -> None:
        contract = self._stable_fixture()
        self._preview(contract)
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        compatibility["known_incompatible_host_versions"] = [
            {"reason": "workflow regression", "version": "2.1.200"}
        ]
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["host_version"] = "2.1.200"
        rows[0]["tier"] = "capability-qualified"
        errors = validate_contract(contract)
        self.assertTrue(any("known-incompatible" in error for error in errors), errors)

        rows[0]["tier"] = "unsupported"
        self.assertEqual(validate_contract(contract), [])

    def test_optional_profile_higher_floor_controls_admission(self) -> None:
        contract = self._stable_fixture()
        self._preview(contract)
        compatibility = contract["compatibility"]
        assert isinstance(compatibility, dict)
        compatibility["optional_profile_floors"] = {
            "research-os": {
                "minimum_host_version": "2.1.200",
                "required_capabilities": ["research-os-capability"],
            }
        }
        rows = compatibility["support_rows"]
        assert isinstance(rows, list) and rows
        assert isinstance(rows[0], dict)
        rows[0]["surface"] = "research-os"
        rows[0]["host_version"] = "2.1.199"
        rows[0]["tier"] = "capability-qualified"
        rows[0]["optional_profile_versions"] = {"research-os": "1.0.0"}
        evidence = rows[0]["capability_evidence"]
        assert isinstance(evidence, dict)
        evidence["passed_capabilities"] = ["research-os-capability"]
        errors = validate_contract(contract)
        self.assertTrue(
            any("below the research-os profile minimum" in error for error in errors),
            errors,
        )

        rows[0]["host_version"] = "2.1.200"
        self.assertEqual(validate_contract(contract), [])


class ReleaseContractPreviewAndClaimTests(unittest.TestCase):
    forbidden_claims = {
        "provider_neutral_equal_parity": "provider-neutral",
        "blanket_cross_platform_latest": "all platforms",
        "provider_wide": "all providers",
        "model_wide": "all models",
        "official_product": "official Anthropic product",
        "replacement": "Claude Code replacement",
        "universal_gateway": "universal gateway",
        "bundled_companion": "bundled companion library",
        "unsupported_renderer": "cross-platform renderer",
        "asd_conformance": "ASD-STE100 compliant",
        "security_completeness": "complete security",
    }

    def _preview_fixture(self) -> dict[str, object]:
        return load_contract_fixture("preview-valid.json")

    def test_preview_fixture_is_side_by_side_and_does_not_inherit_stable_state(self) -> None:
        preview = self._preview_fixture()
        self.assertEqual(validate_contract(preview), [])

        channels = preview["channels"]
        assert isinstance(channels, dict)
        preview_channel = channels["preview"]
        assert isinstance(preview_channel, dict)
        preview_channel["install_mode"] = "in-place"
        preview_channel["may_overwrite_stable"] = True
        preview_channel["inherits_stable_state"] = True
        errors = validate_contract(preview)
        self.assertTrue(any("preview must install side-by-side" in error for error in errors), errors)
        self.assertTrue(any("preview cannot overwrite stable state" in error for error in errors), errors)
        self.assertTrue(any("preview cannot inherit stable state" in error for error in errors), errors)

    def test_claim_lint_rejects_each_closed_claim_category(self) -> None:
        for category, forbidden_claim in self.forbidden_claims.items():
            with self.subTest(category=category):
                errors = validate_contract(
                    self._preview_fixture(),
                    {f"candidate-{category}.md": f"This candidate says {forbidden_claim}.\n"},
                )
                self.assertTrue(
                    any(f"claim lint [{category}]" in error for error in errors),
                    errors,
                )

    def test_claim_lint_never_scans_historical_prose_outside_its_fixture_root(self) -> None:
        errors = validate_contract(
            self._preview_fixture(),
            outside="Historical prose can say this is a universal gateway.\n",
        )
        self.assertEqual(errors, [])

    def test_claim_lint_refuses_symlink_root_before_scanning_outside_content(self) -> None:
        def plant_escaped_root(root: Path, fixture_root: Path) -> None:
            outside = root / "outside-fixtures"
            outside.mkdir()
            (outside / "candidate.md").write_text(
                "This candidate says universal gateway.\n", encoding="utf-8"
            )
            fixture_root.symlink_to(outside, target_is_directory=True)

        errors = validate_contract(self._preview_fixture(), fixture_setup=plant_escaped_root)
        self.assertTrue(any("fixture root must not be a symlink" in error for error in errors), errors)
        self.assertFalse(any("claim lint [" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
