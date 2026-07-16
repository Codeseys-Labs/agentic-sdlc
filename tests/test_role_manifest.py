"""Conformance tests for the versioned role-contract manifest (R1).

RED-first strategy (spec §5): each fixture mutates the golden manifest to express an
authority or schema violation, and validate_role_manifest MUST flag it. The golden
manifest itself must validate clean. The load-bearing cases (F4) prove the manifest
cannot become a mutable bypass channel around the source-pinned authority digests: a
coordinated edit granting authority fails validation even when every mutable content
digest is correctly repinned, because the authority rules key off the pinned contract
and the role identity, never the manifest's own claim.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
BUNDLE_VALIDATOR = ROOT / "scripts" / "validate_bundle.py"
MANIFEST_PATH = ROOT / "policy" / "role-manifest.v1.json"
FIXTURES = ROOT / "tests" / "fixtures" / "role-manifest"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bundle_validator = load_module("bundle_validator_role_manifest", BUNDLE_VALIDATOR)


class RoleManifestConformanceTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.golden = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def _validate_manifest(self, manifest: dict) -> bundle_validator.Validation:
        """Run validate_role_manifest against a temp root whose only mutation is the manifest.

        agents/ and the pinned normative contract are copied verbatim so every cross-check
        resolves against the real pinned bytes; only policy/role-manifest.v1.json varies.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy").mkdir()
            (root / "policy" / "role-manifest.v1.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            (root / "policy" / "runtime-assignment-normative-contract-v1.json").write_bytes(
                bundle_validator.NORMATIVE_CONTRACT_PATH.read_bytes()
            )
            shutil.copytree(ROOT / "agents", root / "agents")
            result = bundle_validator.Validation()
            bundle_validator.validate_role_manifest(root, result)
            return result

    def assert_rejects(self, manifest: dict, needle: str = "role-manifest") -> None:
        result = self._validate_manifest(manifest)
        self.assertTrue(
            any(needle in error for error in result.errors),
            f"expected an error containing {needle!r}; got {result.errors}",
        )

    def assert_accepts(self, manifest: dict) -> None:
        result = self._validate_manifest(manifest)
        self.assertEqual(result.errors, [], result.errors)

    # ---- baseline: the shipped manifest and the packaged golden both validate clean ----

    def test_shipped_manifest_validates_against_real_tree(self) -> None:
        result = bundle_validator.Validation()
        bundle_validator.validate_role_manifest(ROOT, result)
        self.assertEqual(result.errors, [], result.errors)

    def test_golden_manifest_is_green_in_harness(self) -> None:
        self.assert_accepts(self.golden)

    # ---- F1 — schema validity ----

    def test_f1_unknown_top_level_key_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["unexpected"] = True
        self.assert_rejects(m, "top-level keys")

    def test_f1_wrong_schema_version_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["schema_version"] = "role-manifest/v2"
        self.assert_rejects(m, "schema_version")

    def test_f1_role_missing_required_key_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        del m["roles"]["implementer"]["capabilities"]
        self.assert_rejects(m, "missing keys")

    def test_f1_role_unknown_key_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["implementer"]["backdoor"] = True
        self.assert_rejects(m, "unknown keys")

    # ---- F2 — roster completeness & counts ----

    def test_f2_missing_role_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        del m["roles"]["critic"]
        self.assert_rejects(m, "logical roles")

    def test_f2_extra_role_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["project_specialist"] = copy.deepcopy(m["roles"]["reviewer"])
        self.assert_rejects(m, "logical roles")

    def test_f2_wrong_counts_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["counts"]["projection_files"] = 30
        self.assert_rejects(m, "counts")

    def test_f2_research_role_gaining_claude_projection_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["theorist"]["projections"]["claude"] = copy.deepcopy(
            self.golden["roles"]["reviewer"]["projections"]["claude"]
        )
        self.assert_rejects(m, "projections must be")

    # ---- F3 — digest coexistence ----

    def test_f3_mutated_content_digest_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["reviewer"]["projections"]["claude"]["content_digest"] = "0" * 64
        self.assert_rejects(m, "content_digest differs")

    def test_f3_relaxed_sandbox_mode_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        # repo_cartographer is workspace-write in the pinned contract; a manifest cannot
        # relax it to read-only because the check compares against the pinned value.
        m["roles"]["repo_cartographer"]["projections"]["codex"]["sandbox_mode"] = "read-only"
        self.assert_rejects(m, "sandbox_mode differs")

    def test_f3_normative_contract_binding_drift_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["generated_from"]["normative_contract_sha256"] = "f" * 64
        self.assert_rejects(m, "normative_contract_sha256")

    # ---- F4 — authority cross-checks (the anti-bypass suite) ----

    def test_f4_fan_in_authority_on_planner_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["fan_in_authority"] = "authorized-executor"
        self.assert_rejects(m, "fan_in_authority must be none")

    def test_f4_integrator_downgraded_fan_in_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["integrator"]["fan_in_authority"] = "none"
        self.assert_rejects(m, "integrator fan_in_authority")

    def test_f4_queue_mutate_on_research_director_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["research_director"]["queue_authority"] = "mutate"
        self.assert_rejects(m, "queue_authority")

    def test_f4_queue_authority_on_planner_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["queue_authority"] = "read-only"
        self.assert_rejects(m, "queue_authority")

    def test_f4_reviewer_advisory_false_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["reviewer"]["advisory_only"] = False
        self.assert_rejects(m, "advisory_only=true")

    def test_f4_critic_advisory_false_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["critic"]["advisory_only"] = False
        self.assert_rejects(m, "advisory_only=true")

    def test_f4_publication_authority_nonzero_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["integrator"]["publication_authority"] = "authorized-publisher"
        self.assert_rejects(m, "publication_authority must be none")

    def test_f4_coordinated_repin_authority_grab_still_fails(self) -> None:
        """CRITICAL: a coordinated edit granting authority fails even with every content
        digest correctly repinned and the normative binding intact. This proves the
        manifest is not a mutable bypass channel around the pinned authority digests.
        """
        fixture = json.loads(
            (FIXTURES / "coordinated-repin-authority-grab.json").read_text(encoding="utf-8")
        )
        # Precondition: the fixture keeps the true normative binding and all pinned digests
        # untouched, so ONLY the authority fields differ from the golden.
        self.assertEqual(
            fixture["generated_from"]["normative_contract_sha256"],
            self.golden["generated_from"]["normative_contract_sha256"],
        )
        for role_id, role in fixture["roles"].items():
            for host, projection in role["projections"].items():
                self.assertEqual(
                    projection["content_digest"],
                    self.golden["roles"][role_id]["projections"][host]["content_digest"],
                    f"{role_id}/{host} digest must remain correctly pinned",
                )
        result = self._validate_manifest(fixture)
        self.assertTrue(
            any("queue_authority" in e for e in result.errors),
            f"director Seeds-mutation grab must fail; got {result.errors}",
        )
        self.assertTrue(
            any("advisory_only=true" in e for e in result.errors),
            f"reviewer outward-authority grab must fail; got {result.errors}",
        )

    # ---- F5 — model-lane guard ----

    def test_f5_exact_model_id_in_model_block_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["model"]["lane_family"] = "frontier"
        m["roles"]["planner"]["model"]["pinned_model"] = "claude-fable-5"
        self.assert_rejects(m, "leaks exact model id")

    def test_f5_resolved_model_id_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["model"]["resolved_model_id"] = "claude-opus-4-8"
        self.assert_rejects(m, "resolved_model_id")

    def test_f5_lane_family_set_to_exact_model_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["model"]["lane_family"] = "gpt-5.6-sol"
        self.assert_rejects(m, "lane_family")

    def test_f5_exact_id_leak_in_model_value_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["model"]["effort_band_hint"] = "high claude-opus-4-8"
        self.assert_rejects(m, "leaks exact model id")

    def test_f5_wrong_runtime_model_source_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["planner"]["model"]["runtime_model_source"] = "caller-default"
        self.assert_rejects(m, "runtime_model_source")

    # ---- F6 — capability declarations (fail-closed) ----

    def test_f6_non_researcher_delivery_web_required_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["implementer"]["capabilities"]["web_access"] = "required"
        m["roles"]["implementer"]["capabilities"]["network"] = "required"
        self.assert_rejects(m)

    def test_f6_web_consumer_downgraded_to_none_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["literature_scout"]["capabilities"]["web_access"] = "none"
        m["roles"]["literature_scout"]["capabilities"]["network"] = "none"
        self.assert_rejects(m)

    def test_f6_web_required_without_network_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["researcher"]["capabilities"]["network"] = "none"
        self.assert_rejects(m, "implies network=required")

    # ---- F7 — cartography discriminant ----

    def test_f7_research_memory_map_tagged_delivery_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["repo_cartographer"]["cartography"]["map_kind"] = "delivery"
        self.assert_rejects(m, "repo_cartographer cartography")

    def test_f7_delivery_cartographer_tagged_durable_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["cartographer"]["cartography"]["persistence"] = "durable"
        self.assert_rejects(m, "cartographer cartography")

    def test_f7_cartography_on_non_map_role_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["implementer"]["cartography"] = {"map_kind": "delivery", "persistence": "ephemeral"}
        self.assert_rejects(m, "must not declare cartography")

    # ---- F8 — submission-contract tagging ----

    def test_f8_delivery_role_tagged_research_ledger_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["reviewer"]["projections"]["claude"]["submission_contract"] = "research-ledger"
        self.assert_rejects(m, "submission_contract must be")

    def test_f8_research_role_tagged_eight_heading_rejected(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["theorist"]["projections"]["codex"]["submission_contract"] = "eight-heading"
        self.assert_rejects(m, "submission_contract must be")

    # ---- artifact vocabulary ----

    def test_artifacts_must_be_standard_names(self) -> None:
        m = copy.deepcopy(self.golden)
        m["roles"]["implementer"]["artifacts"]["produced"] = ["Blueprint"]
        self.assert_rejects(m, "standard artifact names")


if __name__ == "__main__":
    unittest.main()
