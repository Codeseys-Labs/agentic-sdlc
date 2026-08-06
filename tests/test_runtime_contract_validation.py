from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).parents[1]
BUNDLE_VALIDATOR = ROOT / "scripts" / "validate_bundle.py"
RESEARCH_INSTALLER = ROOT / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
RECEIPT_ADMISSION = ROOT / "skills" / "model-tier-rightsizing" / "scripts" / "receipt_admission.py"
NORMATIVE_CONTRACT = ROOT / "policy" / "runtime-assignment-normative-contract-v1.json"
PACKAGED_RECEIPT_POLICY = ROOT / "skills" / "codex-research-os" / "policy" / "runtime-assignment-receipt-v1.json"
PACKAGED_NORMATIVE_CONTRACT = ROOT / "skills" / "codex-research-os" / "policy" / "runtime-assignment-normative-contract-v1.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bundle_validator = load_module("bundle_validator_under_test", BUNDLE_VALIDATOR)
research_installer = load_module("research_installer_under_test", RESEARCH_INSTALLER)
receipt_admission = load_module("receipt_admission_under_test", RECEIPT_ADMISSION)
RECEIPT_POLICY = receipt_admission.parse_no_duplicate_members(
    receipt_admission.POLICY_PATH.read_text(encoding="utf-8")
)


class RuntimeContractValidationTests(unittest.TestCase):
    maxDiff = None

    def test_bundle_validator_semantically_rejects_claude_model_and_effort_pins(self) -> None:
        forms = {
            "quoted": 'name: sdlc-reviewer\ndescription: test\n"model": "claude-sonnet-5"\n"model_reasoning_effort": "high"',
            "escaped explicit key": 'name: sdlc-reviewer\ndescription: test\n"m\\u006fdel": "claude-sonnet-5"\n"model\\x5freasoning\\x5feffort": "high"',
            "explicit key": 'name: sdlc-reviewer\ndescription: test\n? "model"\n: "claude-sonnet-5"\n? model_reasoning_effort\n: high',
            "flow map": '{name: sdlc-reviewer, description: test, model: claude-sonnet-5, model_reasoning_effort: high}',
        }
        for name, metadata in forms.items():
            with self.subTest(form=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                agent = root / "agents" / "claude" / "sdlc-reviewer.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    "---\n"
                    f"{metadata}\n"
                    "---\n",
                    encoding="utf-8",
                )
                result = bundle_validator.Validation()
                bundle_validator.validate_agents(root, result)

                self.assertIn("agents/claude/sdlc-reviewer.md: static model is forbidden", result.errors)
                self.assertIn(
                    "agents/claude/sdlc-reviewer.md: static model_reasoning_effort is forbidden",
                    result.errors,
                )

    def test_bundle_validator_semantically_rejects_skill_model_and_effort_pins(self) -> None:
        """A vendored or authored skill must not pin a model either.

        validate_agents already covers agents/. Skills were unchecked, so a third-party
        SKILL.md carrying `model:` passed silently. The check must parse semantically: the raw
        frontmatter of the real `model-tier-rightsizing` skill contains the substring "model"
        in its own `name:`, so a substring test false-positives on a shipped skill, and a
        line-anchored regex would still miss the quoted and \\u-escaped key forms below.
        """
        forms = {
            "plain": "name: pin-probe\ndescription: test\nmodel: opus\nmodel_reasoning_effort: high",
            "quoted": 'name: pin-probe\ndescription: test\n"model": "claude-opus-5"',
            "escaped explicit key": 'name: pin-probe\ndescription: test\n"m\\u006fdel": "claude-opus-5"',
            "flow map": "{name: pin-probe, description: test, model: claude-opus-5}",
        }
        for name, metadata in forms.items():
            with self.subTest(form=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                skill = root / "skills" / "pin-probe" / "SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(f"---\n{metadata}\n---\n", encoding="utf-8")
                result = bundle_validator.Validation()
                bundle_validator.validate_skills(root, result)

                self.assertIn("pin-probe: static model is forbidden", result.errors)

    def test_bundle_validator_accepts_shipped_skill_names_containing_model(self) -> None:
        """The shipped `model-tier-rightsizing` skill must not trip the pin check."""
        result = bundle_validator.Validation()
        bundle_validator.validate_skills(ROOT, result)
        self.assertEqual(
            [error for error in result.errors if "static model" in error],
            [],
            "a skill whose name merely contains 'model' must not be reported as pinning one",
        )

    def test_bundle_validator_semantically_parses_yaml_without_system_ruby(self) -> None:
        metadata = 'name: sdlc-reviewer\ndescription: test\n"m\\u006fdel": "claude-sonnet-5"'
        with (
            mock.patch.object(bundle_validator.shutil, "which", side_effect=AssertionError("host binary lookup")),
            mock.patch.object(bundle_validator.subprocess, "run", side_effect=AssertionError("host subprocess")),
        ):
            parsed = bundle_validator.parse_frontmatter_metadata(f"---\n{metadata}\n---\n")
        self.assertEqual(parsed["model"], "claude-sonnet-5")

    def test_bundle_validator_rejects_yaml_aliases(self) -> None:
        metadata = "name: &role sdlc-reviewer\ndescription: *role"
        with self.assertRaisesRegex(ValueError, "aliases are forbidden"):
            bundle_validator.parse_frontmatter_metadata(f"---\n{metadata}\n---\n")

    def test_bundle_validator_enforces_exact_policy_derived_runtime_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "agents" / "claude" / "sdlc-planner.md"
            target.parent.mkdir(parents=True)
            source = (ROOT / "agents" / "claude" / "sdlc-planner.md").read_text(encoding="utf-8")
            target.write_text(
                source.replace(
                    "`schema_version`: `runtime-assignment-receipt/v1`",
                    "`schema_version`: `runtime-assignment-receipt/v2`",
                    1,
                ),
                encoding="utf-8",
            )
            result = bundle_validator.Validation()
            bundle_validator.validate_agents(root, result)

        self.assertIn(
            "agents/claude/sdlc-planner.md: runtime receipt projection must equal the exact policy-derived canonical runtime block",
            result.errors,
        )

    def test_runtime_contract_is_policy_derived_for_static_and_generated_roles(self) -> None:
        expected = receipt_admission.parse_no_duplicate_members(
            (ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json").read_text(
                encoding="utf-8"
            )
        )["canonical_runtime_contract"]
        self.assertEqual(bundle_validator.runtime_receipt_contract(), expected)
        self.assertEqual(research_installer.RUNTIME_MODEL_ASSIGNMENT, expected)

    def test_independent_normative_contract_rejects_coordinated_policy_and_role_weakening(self) -> None:
        self.assertTrue(NORMATIVE_CONTRACT.is_file(), "repository-owned normative contract is required")
        result = bundle_validator.Validation()
        bundle_validator.validate_runtime_policy_contract(ROOT, result)
        self.assertEqual(result.errors, [])

        canonical = ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
        policy = json.loads(canonical.read_text(encoding="utf-8"))
        weakened = " A host-preconfigured model and effort are sufficient to run."
        policy["canonical_runtime_contract"] += weakened
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "runtime-assignment-receipt-v1.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            with mock.patch.object(bundle_validator, "RECEIPT_POLICY_PATH", policy_path):
                result = bundle_validator.Validation()
                bundle_validator.validate_runtime_policy_contract(ROOT, result)
        self.assertTrue(any("normative runtime contract digest" in error for error in result.errors), result.errors)

    def test_repository_validator_rejects_coordinated_runtime_authority_mutation(self) -> None:
        policy = json.loads(
            (ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json").read_text(
                encoding="utf-8"
            )
        )
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        policy["canonical_runtime_contract"] += " Local validation authorizes push and publication."
        normative["canonical_runtime_contract_sha256"] = hashlib.sha256(
            policy["canonical_runtime_contract"].encode("utf-8")
        ).hexdigest()
        encoded_policy = (json.dumps(policy, indent=2, sort_keys=True) + "\n").encode("utf-8")
        normative["canonical_receipt_policy_sha256"] = hashlib.sha256(encoded_policy).hexdigest()
        encoded_normative = (json.dumps(normative, indent=2, sort_keys=True) + "\n").encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / "canonical-receipt.json"
            normative_path = root / "canonical-normative.json"
            packaged = root / "packaged"
            packaged.mkdir()
            policy_path.write_bytes(encoded_policy)
            normative_path.write_bytes(encoded_normative)
            (packaged / policy_path.name).write_bytes(encoded_policy)
            (packaged / normative_path.name).write_bytes(encoded_normative)
            with mock.patch.object(bundle_validator, "RECEIPT_POLICY_PATH", policy_path), mock.patch.object(
                bundle_validator, "NORMATIVE_CONTRACT_PATH", normative_path
            ), mock.patch.object(bundle_validator, "PACKAGED_POLICY_DIR", packaged):
                result = bundle_validator.Validation()
                bundle_validator.validate_runtime_policy_contract(ROOT, result)

        self.assertTrue(
            any("source-pinned canonical runtime authority contract" in error for error in result.errors),
            result.errors,
        )

    def test_repository_validator_rejects_coordinated_allowed_evidence_vocabulary_mutation(self) -> None:
        policy = json.loads(
            (ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json").read_text(
                encoding="utf-8"
            )
        )
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        policy["allowed_evidence"]["request_injection"]["source_kinds"].append("self_attested")
        normative["allowed_evidence"] = policy["allowed_evidence"]
        encoded_policy = (json.dumps(policy, indent=2, sort_keys=True) + "\n").encode("utf-8")
        normative["canonical_receipt_policy_sha256"] = hashlib.sha256(encoded_policy).hexdigest()
        encoded_normative = (json.dumps(normative, indent=2, sort_keys=True) + "\n").encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / "canonical-receipt.json"
            normative_path = root / "canonical-normative.json"
            packaged = root / "packaged"
            packaged.mkdir()
            policy_path.write_bytes(encoded_policy)
            normative_path.write_bytes(encoded_normative)
            (packaged / policy_path.name).write_bytes(encoded_policy)
            (packaged / normative_path.name).write_bytes(encoded_normative)
            with mock.patch.object(bundle_validator, "RECEIPT_POLICY_PATH", policy_path), mock.patch.object(
                bundle_validator, "NORMATIVE_CONTRACT_PATH", normative_path
            ), mock.patch.object(bundle_validator, "PACKAGED_POLICY_DIR", packaged):
                result = bundle_validator.Validation()
                bundle_validator.validate_runtime_policy_contract(ROOT, result)

        self.assertTrue(
            any("allowed_evidence vocabulary" in error for error in result.errors),
            result.errors,
        )

    def test_repository_validator_rejects_certified_tuple_regression_after_coordinated_repin(self) -> None:
        policy = json.loads(
            (ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json").read_text(
                encoding="utf-8"
            )
        )
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        removed = policy["certified_request_tuples"].pop()
        normative["certified_request_tuples"].remove(removed)
        encoded_policy = (json.dumps(policy, indent=2, sort_keys=True) + "\n").encode("utf-8")
        normative["canonical_receipt_policy_sha256"] = hashlib.sha256(encoded_policy).hexdigest()
        encoded_normative = (json.dumps(normative, indent=2, sort_keys=True) + "\n").encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / "canonical-receipt.json"
            normative_path = root / "canonical-normative.json"
            packaged = root / "packaged"
            packaged.mkdir()
            policy_path.write_bytes(encoded_policy)
            normative_path.write_bytes(encoded_normative)
            (packaged / policy_path.name).write_bytes(encoded_policy)
            (packaged / normative_path.name).write_bytes(encoded_normative)
            with mock.patch.object(bundle_validator, "RECEIPT_POLICY_PATH", policy_path), mock.patch.object(
                bundle_validator, "NORMATIVE_CONTRACT_PATH", normative_path
            ), mock.patch.object(bundle_validator, "PACKAGED_POLICY_DIR", packaged):
                result = bundle_validator.Validation()
                bundle_validator.validate_runtime_policy_contract(ROOT, result)

        self.assertIn(
            "runtime receipt policy certified request tuples differ from the source-pinned model/context matrix",
            result.errors,
        )

        self.assertTrue(PACKAGED_RECEIPT_POLICY.is_file(), "standalone Research OS policy snapshot is required")
        self.assertTrue(PACKAGED_NORMATIVE_CONTRACT.is_file(), "standalone Research OS normative snapshot is required")
        self.assertEqual(
            PACKAGED_RECEIPT_POLICY.read_bytes(),
            (ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json").read_bytes(),
        )
        self.assertEqual(PACKAGED_NORMATIVE_CONTRACT.read_bytes(), NORMATIVE_CONTRACT.read_bytes())

    def test_normative_contract_pins_exact_models_pairs_effort_context_and_managed_rosters(self) -> None:
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        receipt_policy_path = ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
        receipt_policy = json.loads(receipt_policy_path.read_text(encoding="utf-8"))
        self.assertEqual(
            normative["exact_model_provider_map"],
            {
                "claude-fable-5": "anthropic",
                "claude-opus-4-8": "anthropic",
                "claude-sonnet-5": "anthropic",
                "gpt-5.6-sol": "openai",
                "gpt-5.6-terra": "openai",
                "gpt-5.6-luna": "openai",
            },
        )
        self.assertEqual(
            normative["exact_model_pairs"],
            {
                "frontier": ["gpt-5.6-sol", "claude-fable-5"],
                "judgment": ["gpt-5.6-terra", "claude-opus-4-8"],
                "volume": ["gpt-5.6-luna", "claude-sonnet-5"],
            },
        )
        self.assertEqual(normative["allowed_efforts"], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual(
            normative["production_efforts_by_model"],
            {
                "claude-fable-5": ["xhigh", "max"],
                "claude-opus-4-8": ["high", "xhigh"],
                "claude-sonnet-5": ["high", "xhigh"],
                "gpt-5.6-sol": ["high", "xhigh"],
                "gpt-5.6-terra": ["xhigh", "max"],
                "gpt-5.6-luna": ["high", "xhigh"],
            },
        )
        self.assertEqual(normative["allowed_context_forms"], ["base", "[1m]"])
        self.assertEqual(
            normative["certified_context_forms_by_model"],
            {
                "claude-fable-5": ["base"],
                "claude-opus-4-8": ["base"],
                "claude-sonnet-5": ["base"],
                "gpt-5.6-sol": ["base", "[1m]"],
                "gpt-5.6-terra": ["base", "[1m]"],
                "gpt-5.6-luna": ["base", "[1m]"],
            },
        )
        self.assertEqual(
            normative["canonical_receipt_policy_sha256"],
            hashlib.sha256(receipt_policy_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            normative["canonical_runtime_contract_sha256"],
            hashlib.sha256(receipt_policy["canonical_runtime_contract"].encode("utf-8")).hexdigest(),
        )
        self.assertIn("validated only for canonical internal consistency", normative["validation_only_semantics"])
        self.assertIn("proves neither intelligence", normative["one_million_context_semantics"])
        self.assertEqual(normative["managed_roles"]["global"]["count"], 14)
        self.assertEqual(len(normative["managed_roles"]["global"]["manifest_sha256"]), 14)
        self.assertEqual(normative["managed_roles"]["research"]["count"], 17)
        self.assertEqual(len(normative["managed_roles"]["research"]["roles"]), 17)
        for role, spec in normative["managed_roles"]["research"]["roles"].items():
            with self.subTest(role=role):
                self.assertIn(spec["sandbox_mode"], {"read-only", "workspace-write"})
                self.assertRegex(spec["description_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(spec["developer_instructions_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(spec["manifest_sha256"], r"^[0-9a-f]{64}$")

    def test_bundle_validator_rejects_unknown_top_level_installable_role_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "agents", root / "agents")
            unknown = root / "agents" / "claude" / "project_specialist.md"
            unknown.write_text((ROOT / "agents" / "claude" / "sdlc-reviewer.md").read_text(encoding="utf-8"), encoding="utf-8")
            result = bundle_validator.Validation()
            bundle_validator.validate_managed_role_contract(root, result)

        self.assertTrue(any("managed role roster" in error for error in result.errors), result.errors)

    def test_bundle_validator_source_pins_global_roster_despite_coordinated_repin(self) -> None:
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "agents", root / "agents")
            original = root / "agents" / "claude" / "sdlc-cartographer.md"
            replacement = root / "agents" / "claude" / "project_specialist.md"
            original.rename(replacement)
            replacement.write_text(
                replacement.read_text(encoding="utf-8").replace("name: sdlc-cartographer", "name: project_specialist", 1),
                encoding="utf-8",
            )
            global_spec = normative["managed_roles"]["global"]
            original_key = "agents/claude/sdlc-cartographer.md"
            replacement_key = "agents/claude/project_specialist.md"
            global_spec["manifest_sha256"][replacement_key] = hashlib.sha256(replacement.read_bytes()).hexdigest()
            global_spec["manifest_sha256"].pop(original_key)
            with mock.patch.object(bundle_validator, "normative_runtime_contract", return_value=normative):
                result = bundle_validator.Validation()
                bundle_validator.validate_managed_role_contract(root, result)

        self.assertIn("managed role roster must contain exactly the 14 global SDLC roles", result.errors)

    def test_bundle_validator_source_pins_research_roster_despite_coordinated_repin(self) -> None:
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "agents", root / "agents")
            original = root / "agents" / "codex" / "research" / "safety_reviewer.toml"
            replacement = root / "agents" / "codex" / "research" / "project_specialist.toml"
            original.rename(replacement)
            data = tomllib.loads(replacement.read_text(encoding="utf-8"))
            data["name"] = "project_specialist"
            encoded = (
                f'name = "{data["name"]}"\n'
                f'description = "{data["description"]}"\n'
                f'sandbox_mode = "{data["sandbox_mode"]}"\n\n'
                'developer_instructions = """\n'
                f'{data["developer_instructions"]}'
                '"""\n'
            )
            replacement.write_text(encoded, encoding="utf-8")
            research_spec = normative["managed_roles"]["research"]
            role_spec = research_spec["roles"].pop("safety_reviewer")
            role_spec.update(
                path="agents/codex/research/project_specialist.toml",
                description_sha256=hashlib.sha256(data["description"].encode()).hexdigest(),
                developer_instructions_sha256=hashlib.sha256(data["developer_instructions"].encode()).hexdigest(),
                manifest_sha256=hashlib.sha256(replacement.read_bytes()).hexdigest(),
            )
            research_spec["roles"]["project_specialist"] = role_spec
            with mock.patch.object(bundle_validator, "normative_runtime_contract", return_value=normative):
                result = bundle_validator.Validation()
                bundle_validator.validate_managed_role_contract(root, result)

        self.assertIn("managed role roster must contain exactly the 17 Research OS roles", result.errors)

    def test_bundle_validator_source_pins_protected_role_authority_despite_coordinated_repin(self) -> None:
        normative = json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8"))
        mutations = {
            "director Seeds": (
                "research_director",
                "The Research Director may create and mutate Seeds.",
            ),
            "global reviewer push": (
                "sdlc-reviewer",
                "Reviewer roles may push, publish, and authorize outward effects.",
            ),
            "research reviewer publish": (
                "safety_reviewer",
                "Reviewer roles may push, publish, and authorize outward effects.",
            ),
        }
        for name, (role, addition) in mutations.items():
            normative = copy.deepcopy(json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8")))
            with self.subTest(mutation=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / "agents", root / "agents")
                if role == "sdlc-reviewer":
                    paths = [
                        root / "agents" / "claude" / "sdlc-reviewer.md",
                        root / "agents" / "codex" / "sdlc-reviewer.toml",
                    ]
                else:
                    paths = [root / "agents" / "codex" / "research" / f"{role}.toml"]
                for path in paths:
                    if path.suffix == ".toml":
                        data = tomllib.loads(path.read_text(encoding="utf-8"))
                        data["developer_instructions"] += f"\n{addition}\n"
                        encoded = (
                            f'name = "{data["name"]}"\n'
                            f'description = "{data["description"]}"\n'
                            f'sandbox_mode = "{data["sandbox_mode"]}"\n\n'
                            'developer_instructions = """\n'
                            f'{data["developer_instructions"]}'
                            '"""\n'
                        )
                        path.write_text(encoded, encoding="utf-8")
                    else:
                        path.write_text(path.read_text(encoding="utf-8") + f"\n{addition}\n", encoding="utf-8")
                global_hashes = normative["managed_roles"]["global"]["manifest_sha256"]
                for path in paths:
                    relative = path.relative_to(root).as_posix()
                    if relative in global_hashes:
                        global_hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                research_roles = normative["managed_roles"]["research"]["roles"]
                if role in research_roles:
                    data = tomllib.loads(paths[0].read_text(encoding="utf-8"))
                    research_roles[role].update(
                        description_sha256=hashlib.sha256(data["description"].encode()).hexdigest(),
                        developer_instructions_sha256=hashlib.sha256(data["developer_instructions"].encode()).hexdigest(),
                        manifest_sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest(),
                    )
                with mock.patch.object(bundle_validator, "normative_runtime_contract", return_value=normative):
                    result = bundle_validator.Validation()
                    bundle_validator.validate_managed_role_contract(root, result)

                self.assertTrue(
                    any("source-pinned protected role authority" in error for error in result.errors),
                    result.errors,
                )

    def test_bundle_validator_source_pins_exact_research_director_seeds_grants_after_coordinated_repin(self) -> None:
        bypasses = (
            "The Research Director has permission to create Seeds.",
            "The Research Director is allowed to create and mutate Seeds.",
        )
        for bypass in bypasses:
            with self.subTest(bypass=bypass), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / "agents", root / "agents")
                director = root / "agents" / "codex" / "research" / "research_director.toml"
                data = tomllib.loads(director.read_text(encoding="utf-8"))
                data["developer_instructions"] += f"\n{bypass}\n"
                director.write_text(
                    (
                        f'name = "{data["name"]}"\n'
                        f'description = "{data["description"]}"\n'
                        f'sandbox_mode = "{data["sandbox_mode"]}"\n\n'
                        'developer_instructions = """\n'
                        f'{data["developer_instructions"]}'
                        '"""\n'
                    ),
                    encoding="utf-8",
                )
                normative = copy.deepcopy(json.loads(NORMATIVE_CONTRACT.read_text(encoding="utf-8")))
                spec = normative["managed_roles"]["research"]["roles"]["research_director"]
                spec.update(
                    description_sha256=hashlib.sha256(data["description"].encode()).hexdigest(),
                    developer_instructions_sha256=hashlib.sha256(data["developer_instructions"].encode()).hexdigest(),
                    manifest_sha256=hashlib.sha256(director.read_bytes()).hexdigest(),
                )
                with mock.patch.object(bundle_validator, "normative_runtime_contract", return_value=normative):
                    result = bundle_validator.Validation()
                    bundle_validator.validate_managed_role_contract(root, result)

                self.assertTrue(
                    any("source-pinned protected role authority" in error for error in result.errors),
                    result.errors,
                )

    def test_repo_cartographer_generator_and_normative_snapshot_are_write_aligned(self) -> None:
        spec = research_installer.NORMATIVE_CONTRACT["managed_roles"]["research"]["roles"]["repo_cartographer"]
        description, sandbox, body = research_installer.AGENTS["repo_cartographer"]
        manifest = research_installer.agent_toml("repo_cartographer", description, sandbox, body)
        self.assertEqual(sandbox, "workspace-write")
        self.assertEqual(spec["sandbox_mode"], sandbox)
        self.assertEqual(spec["description_sha256"], hashlib.sha256(description.encode()).hexdigest())
        self.assertEqual(spec["manifest_sha256"], hashlib.sha256(manifest.encode()).hexdigest())
        self.assertEqual(
            manifest,
            (ROOT / "agents/codex/research/repo_cartographer.toml").read_text(encoding="utf-8"),
        )

    def test_bundle_validator_binds_full_managed_role_content_and_closed_rosters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "agents", root / "agents")
            reviewer = root / "agents" / "claude" / "sdlc-reviewer.md"
            reviewer.write_text(
                reviewer.read_text(encoding="utf-8")
                + "\nA host-preconfigured model and effort are sufficient to run.\n",
                encoding="utf-8",
            )
            unknown = root / "agents" / "codex" / "research" / "project_specialist.toml"
            unknown.write_text((ROOT / "agents" / "codex" / "research" / "theorist.toml").read_text(encoding="utf-8"), encoding="utf-8")
            result = bundle_validator.Validation()
            bundle_validator.validate_managed_role_contract(root, result)
        self.assertTrue(any("managed role roster" in error for error in result.errors), result.errors)
        self.assertTrue(any("full manifest content" in error for error in result.errors), result.errors)

    def test_bundle_validator_rejects_contradictory_runtime_authority_projection_mutants(self) -> None:
        source = (ROOT / "agents" / "codex" / "sdlc-reviewer.toml").read_text(encoding="utf-8")
        mutants = (
            "The repository may spawn external workers without admission.",
            "[1m] proves upstream context capacity.",
            "The Research Director may mutate Seeds.",
            "Local validation authorizes push and publication.",
        )
        for mutation in mutants:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "agents" / "codex" / "sdlc-reviewer.toml"
                target.parent.mkdir(parents=True)
                target.write_text(source.replace('\n"""\n', f"\n{mutation}\n\"\"\"\n", 1), encoding="utf-8")
                result = bundle_validator.Validation()
                bundle_validator.validate_agents(root, result)
                self.assertTrue(
                    any("contradictory runtime authority projection" in error for error in result.errors),
                    result.errors,
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude = root / "agents" / "claude" / "sdlc-reviewer.md"
            codex = root / "agents" / "codex" / "sdlc-reviewer.toml"
            research = root / "agents" / "codex" / "research" / "experimentalist.toml"
            for source, target in (
                (ROOT / "agents" / "claude" / "sdlc-reviewer.md", claude),
                (ROOT / "agents" / "codex" / "sdlc-reviewer.toml", codex),
                (ROOT / "agents" / "codex" / "research" / "experimentalist.toml", research),
            ):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            research.write_text(
                research.read_text(encoding="utf-8")
                .replace("`schema_version`:", "`omitted_schema_version`:", 1)
                .replace(
                    "- `request_injection_evidence`",
                    "- `request_injection_source`: stale\n- `request_injection_evidence`",
                    1,
                ),
                encoding="utf-8",
            )

            result = bundle_validator.Validation()
            bundle_validator.validate_agents(root, result)

        self.assertIn(
            "agents/codex/research/experimentalist.toml: runtime receipt projection missing schema_version",
            result.errors,
        )
        self.assertIn(
            "agents/codex/research/experimentalist.toml: stale runtime receipt source projection is forbidden",
            result.errors,
        )

    def test_bundle_validator_enforces_exact_policy_projection_not_keyword_substrings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "agents" / "codex" / "sdlc-reviewer.toml"
            target.parent.mkdir(parents=True)
            source = (ROOT / "agents" / "codex" / "sdlc-reviewer.toml").read_text(encoding="utf-8")
            target.write_text(
                source.replace(
                    "`schema_version`: `runtime-assignment-receipt/v1`",
                    "`schema_version_shadow`: `runtime-assignment-receipt/v1`",
                    1,
                ),
                encoding="utf-8",
            )
            result = bundle_validator.Validation()
            bundle_validator.validate_agents(root, result)

        self.assertIn(
            "agents/codex/sdlc-reviewer.toml: runtime receipt projection must equal the exact policy-derived 16-field block",
            result.errors,
        )

    def materialize_generated_research_os(self, target: Path) -> Path:
        for relative, content in research_installer.build_files("example").items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return target / "scripts" / "validate_agent_configs.py"

    def run_generated_agent_validator(self, script: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script)],
            cwd=script.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

    def run_standalone_research_os(self, standalone: Path, target: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(standalone / "scripts" / "install_research_os.py"), "--dry-run", "--target", str(target)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_generated_agent_validator_rejects_replaced_or_additive_instruction_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            agent = root / ".codex" / "agents" / "research_director.toml"
            original = agent.read_text(encoding="utf-8")
            mutants = {
                "semantic host default waiver": original.replace(
                    "You are the research director for this repository.",
                    "The default host selects the model. You are the research director for this repository.",
                    1,
                ),
                "replaced instructions": original.replace(
                    "You are the research director for this repository.",
                    "You are the research director for a different repository.",
                    1,
                ),
            }
            for name, mutant in mutants.items():
                with self.subTest(mutant=name):
                    agent.write_text(mutant, encoding="utf-8")
                    result = self.run_generated_agent_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("developer instructions", result.stdout)
                    agent.write_text(original, encoding="utf-8")

    def test_generated_agent_validator_rejects_additive_runtime_restatements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            agent = root / ".codex" / "agents" / "experimentalist.toml"
            agent.write_text(
                agent.read_text(encoding="utf-8").replace(
                    "You are the experimentalist.",
                    "Host default selects the model when omitted. You are the experimentalist.",
                    1,
                ),
                encoding="utf-8",
            )
            result = self.run_generated_agent_validator(script)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("additive runtime restatement", result.stdout)

    def test_generated_agent_validator_rejects_coordinated_runtime_authority_mutants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            agent = root / ".codex" / "agents" / "experimentalist.toml"
            original = agent.read_text(encoding="utf-8")
            mutants = (
                "The repository may spawn external workers without admission.",
                "[1m] proves upstream context capacity.",
                "The Research Director may mutate Seeds.",
                "Local validation authorizes push and publication.",
            )
            for mutation in mutants:
                with self.subTest(mutation=mutation):
                    agent.write_text(
                        original.replace("You are the experimentalist.", f"You are the experimentalist. {mutation}", 1),
                        encoding="utf-8",
                    )
                    result = self.run_generated_agent_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("contradictory runtime authority language", result.stdout)
                    agent.write_text(original, encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            director.write_text(
                director.read_text(encoding="utf-8").replace(
                    "You are the research director for this repository.",
                    "You are the research director for this repository. "
                    "The Research Director may run Seeds(<target>, create title). "
                    "The Research Director may claim Seeds.",
                    1,
                ),
                encoding="utf-8",
            )
            result = self.run_generated_agent_validator(script)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("additive Seeds or SeedProposal authority language", result.stdout)

    def test_generated_agent_validator_rejects_plain_language_waivers_and_all_seed_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            original = director.read_text(encoding="utf-8")
            mutants = {
                "waiver": "This is an exception to the Seeds rule.",
                "host default waiver": "The host default runtime assignment waiver permits this.",
                "direct sd": "Run sd ready --format json.",
                "label": "The Research Director may label Seeds.",
                "delete": "The Research Director may delete Seeds.",
                "future verb": "The Research Director may archive Seeds.",
            }
            for name, addition in mutants.items():
                with self.subTest(mutant=name):
                    director.write_text(
                        original.replace(
                            "You are the research director for this repository.",
                            f"You are the research director for this repository. {addition}",
                            1,
                        ),
                        encoding="utf-8",
                    )
                    result = self.run_generated_agent_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    director.write_text(original, encoding="utf-8")

    def test_generated_agent_validator_rejects_removed_or_duplicated_protected_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            original = director.read_text(encoding="utf-8")
            protected_runtime = research_installer.clean(research_installer.RUNTIME_MODEL_ASSIGNMENT)
            protected_director = research_installer.clean(research_installer.RESEARCH_DIRECTOR_SEEDS_AUTHORITY)
            mutants = {
                "removed runtime": original.replace(protected_runtime, "", 1),
                "duplicated runtime": original.replace(protected_runtime, protected_runtime * 2, 1),
                "removed Seeds": original.replace(protected_director, "", 1),
                "duplicated Seeds": original.replace(protected_director, protected_director * 2, 1),
            }
            for name, mutant in mutants.items():
                with self.subTest(mutant=name):
                    director.write_text(mutant, encoding="utf-8")
                    result = self.run_generated_agent_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    director.write_text(original, encoding="utf-8")

    def test_generated_agent_validator_requires_exact_managed_roster_and_sandbox_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            director.unlink()
            result = self.run_generated_agent_validator(script)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("managed role roster", result.stdout)

            self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            director.write_text(
                director.read_text(encoding="utf-8").replace('sandbox_mode = "workspace-write"', 'sandbox_mode = "danger-full-access"'),
                encoding="utf-8",
            )
            result = self.run_generated_agent_validator(script)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("sandbox_mode", result.stdout)

    def test_generated_agent_validator_fails_closed_for_unknown_project_role(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            unknown = root / ".codex" / "agents" / "project_specialist.toml"
            unknown.write_text(
                research_installer.agent_toml(
                    "project_specialist", "Project-specific role", "read-only", "Read the project.",
                ),
                encoding="utf-8",
            )
            result = self.run_generated_agent_validator(script)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("managed role roster", result.stdout)

    def test_generated_agent_validator_binds_description_and_rejects_seed_authority_inside_runtime_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            original = director.read_text(encoding="utf-8")
            mutants = {
                "description": original.replace(
                    "Coordinates the research team, selects next actions, assigns specialists, and enforces claim discipline.",
                    "Coordinates an unrelated team.",
                    1,
                ),
                "runtime Seeds grant": original.replace(
                    "The receipt is validated only for canonical internal consistency.",
                    "The Research Director may create, claim, update, close, sync, and disposition Seeds. "
                    "The receipt is validated only for canonical internal consistency.",
                    1,
                ),
            }
            for name, mutant in mutants.items():
                with self.subTest(mutant=name):
                    director.write_text(mutant, encoding="utf-8")
                    result = self.run_generated_agent_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    director.write_text(original, encoding="utf-8")

    def test_standalone_research_os_source_pins_roster_despite_normative_repin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standalone = root / "codex-research-os"
            shutil.copytree(RESEARCH_INSTALLER.parents[1], standalone)
            normative_path = standalone / "policy" / "runtime-assignment-normative-contract-v1.json"
            normative = json.loads(normative_path.read_text(encoding="utf-8"))
            roles = normative["managed_roles"]["research"]["roles"]
            replacement = roles.pop("safety_reviewer")
            replacement["path"] = "agents/codex/research/project_specialist.toml"
            roles["project_specialist"] = replacement
            normative_path.write_text(json.dumps(normative, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = self.run_standalone_research_os(standalone, root / "target")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("source-pinned 17 Research OS roles", result.stderr)

    def test_research_os_generator_source_pins_protected_authority(self) -> None:
        mutations = {
            "director": ("research_director", "The Research Director may create and mutate Seeds."),
            "reviewer": ("safety_reviewer", "Reviewer roles may push, publish, and authorize outward effects."),
        }
        for name, (role, addition) in mutations.items():
            with self.subTest(mutation=name):
                description, sandbox, instructions = research_installer.AGENTS[role]
                with mock.patch.dict(
                    research_installer.AGENTS,
                    {role: (description, sandbox, instructions + "\n" + addition)},
                ):
                    with self.assertRaisesRegex(ValueError, "source-pinned protected role authority"):
                        research_installer.validate_source_pinned_role_authority()

    def test_standalone_research_os_source_pins_exact_reviewer_grants_after_coordinated_repin(self) -> None:
        bypasses = (
            "You approve merges and decide release status.",
            "Reviewers are allowed to push and publish review outputs.",
        )
        for bypass in bypasses:
            with self.subTest(bypass=bypass):
                description, sandbox, body = research_installer.AGENTS["safety_reviewer"]
                mutated_agents = {"safety_reviewer": (description, sandbox, body + "\n" + bypass)}
                with mock.patch.dict(research_installer.AGENTS, mutated_agents):
                    instructions = research_installer.developer_instructions_by_role()["safety_reviewer"]
                    manifest = research_installer.agent_toml("safety_reviewer", description, sandbox, body + "\n" + bypass)
                    normative = copy.deepcopy(research_installer.NORMATIVE_CONTRACT)
                    normative["managed_roles"]["research"]["roles"]["safety_reviewer"].update(
                        description_sha256=hashlib.sha256(description.encode()).hexdigest(),
                        developer_instructions_sha256=hashlib.sha256(instructions.encode()).hexdigest(),
                        manifest_sha256=hashlib.sha256(manifest.encode()).hexdigest(),
                    )
                    with mock.patch.object(research_installer, "NORMATIVE_CONTRACT", normative):
                        with self.assertRaisesRegex(ValueError, "source-pinned protected role authority"):
                            research_installer.validate_packaged_managed_roles()

    def test_generated_agent_validator_rejects_exact_reviewer_grants_after_coordinated_repin(self) -> None:
        bypasses = (
            "You approve merges and decide release status.",
            "Reviewers are allowed to push and publish review outputs.",
        )
        for bypass in bypasses:
            with self.subTest(bypass=bypass), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script = self.materialize_generated_research_os(root)
                reviewer = root / ".codex" / "agents" / "safety_reviewer.toml"
                reviewer.write_text(
                    reviewer.read_text(encoding="utf-8").replace(
                        "You are the safety reviewer.",
                        f"You are the safety reviewer. {bypass}",
                        1,
                    ),
                    encoding="utf-8",
                )
                data = tomllib.loads(reviewer.read_text(encoding="utf-8"))
                original_digest = research_installer.SOURCE_PINNED_REVIEWER_INSTRUCTIONS_SHA256["safety_reviewer"]
                repinned_script = script.read_text(encoding="utf-8").replace(
                    f"'developer_instructions_sha256': '{original_digest}'",
                    f"'developer_instructions_sha256': '{hashlib.sha256(data['developer_instructions'].encode()).hexdigest()}'",
                    1,
                )
                script.write_text(repinned_script, encoding="utf-8")
                result = self.run_generated_agent_validator(script)

                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("protected reviewer authority", result.stdout)

    def test_standalone_research_os_rejects_coordinated_packaged_policy_weakening(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standalone = root / "codex-research-os"
            shutil.copytree(RESEARCH_INSTALLER.parents[1], standalone)
            receipt_path = standalone / "policy" / "runtime-assignment-receipt-v1.json"
            normative_path = standalone / "policy" / "runtime-assignment-normative-contract-v1.json"
            original_receipt = receipt_path.read_bytes()
            original_normative = normative_path.read_bytes()
            mutations = {
                "uncertified tuple": lambda receipt, normative: (
                    receipt["certified_request_tuples"].append(["claude-opus-4-8", "low", "[1m]"]),
                    normative["certified_request_tuples"].append(["claude-opus-4-8", "low", "[1m]"]),
                ),
                "claude one-million context": lambda receipt, normative: normative[
                    "certified_context_forms_by_model"
                ]["claude-opus-4-8"].append("[1m]"),
                "runtime authority": lambda receipt, normative: receipt.__setitem__(
                    "canonical_runtime_contract",
                    receipt["canonical_runtime_contract"] + " Local validation authorizes push and publication.",
                ),
                "evidence vocabulary": lambda receipt, normative: receipt[
                    "allowed_evidence"
                ]["request_injection"]["source_kinds"].append("self_attested"),
                "runtime authority": lambda receipt, normative: (
                    receipt.__setitem__(
                        "canonical_runtime_contract",
                        receipt["canonical_runtime_contract"] + " Local validation authorizes push and publication.",
                    ),
                    normative.__setitem__(
                        "canonical_runtime_contract_sha256",
                        hashlib.sha256(receipt["canonical_runtime_contract"].encode("utf-8")).hexdigest(),
                    ),
                ),
                "evidence vocabulary": lambda receipt, normative: (
                    receipt["allowed_evidence"]["request_injection"]["source_kinds"].append("self_attested"),
                    normative.__setitem__("allowed_evidence", receipt["allowed_evidence"]),
                ),
            }
            for name, mutate in mutations.items():
                with self.subTest(mutation=name):
                    receipt = json.loads(original_receipt)
                    normative = json.loads(original_normative)
                    mutate(receipt, normative)
                    encoded_receipt = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
                    normative["canonical_receipt_policy_sha256"] = hashlib.sha256(encoded_receipt).hexdigest()
                    receipt_path.write_bytes(encoded_receipt)
                    normative_path.write_text(json.dumps(normative, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    result = self.run_standalone_research_os(standalone, root / "target")
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    receipt_path.write_bytes(original_receipt)
                    normative_path.write_bytes(original_normative)

    def valid_receipt(self) -> dict[str, object]:
        return receipt_admission.construct_receipt(
            policy=RECEIPT_POLICY,
            requested_model_id="gpt-5.6-terra",
            requested_effort="high",
            requested_context_form="base",
            adapter_id="workflow",
            adapter_version="1.0.0",
            adapter_config={"provider": "openai", "transport": "workflow"},
            model_identity_basis="unambiguous_exact_id_mapping",
            effort_readback_status="unavailable",
            context_readback_status="unavailable",
        )

    def admit_receipt(self, receipt: dict[str, object] | str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RECEIPT_ADMISSION)],
            input=receipt if isinstance(receipt, str) else json.dumps(receipt),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_receipt_validation_emits_a_deterministic_digest_for_bound_evidence(self) -> None:
        receipt = self.valid_receipt()
        self.assertEqual(tuple(receipt), tuple(RECEIPT_POLICY["canonical_receipt_fields"]))
        self.assertEqual(receipt_admission.receipt_errors(receipt, RECEIPT_POLICY), [])
        first = self.admit_receipt(receipt)
        second = self.admit_receipt(self.valid_receipt())

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        validated = json.loads(first.stdout)
        self.assertEqual(validated["status"], "validated")
        self.assertRegex(validated["digest_sha256"], r"^[0-9a-f]{64}$")

    def test_receipt_validation_cross_binds_all_readback_evidence_to_one_assignment(self) -> None:
        first = receipt_admission.construct_receipt(
            policy=RECEIPT_POLICY,
            requested_model_id="gpt-5.6-terra",
            requested_effort="high",
            requested_context_form="base",
            adapter_id="workflow",
            adapter_version="1.0.0",
            adapter_config={"provider": "openai", "transport": "workflow"},
            model_identity_basis="independent_readback",
            observed_provider="openai",
            observed_model_id="gpt-5.6-terra",
            effort_readback_status="verified",
            observed_effort="high",
            context_readback_status="verified",
            observed_context_form="base",
        )
        second = receipt_admission.construct_receipt(
            policy=RECEIPT_POLICY,
            requested_model_id="gpt-5.6-terra",
            requested_effort="high",
            requested_context_form="[1m]",
            adapter_id="workflow",
            adapter_version="1.0.0",
            adapter_config={"provider": "openai", "transport": "workflow"},
            model_identity_basis="independent_readback",
            observed_provider="openai",
            observed_model_id="gpt-5.6-terra",
            effort_readback_status="verified",
            observed_effort="high",
            context_readback_status="verified",
            observed_context_form="[1m]",
        )
        digests = {
            first[field]["assignment_binding_sha256"]
            for field in (
                "model_readback_evidence",
                "effort_readback_evidence",
                "context_readback_evidence",
            )
        }
        self.assertEqual(len(digests), 1)
        for evidence_field in (
            "model_readback_evidence",
            "effort_readback_evidence",
            "context_readback_evidence",
        ):
            with self.subTest(transplanted=evidence_field):
                mutant = json.loads(json.dumps(second))
                mutant[evidence_field] = first[evidence_field]
                errors = receipt_admission.receipt_errors(mutant, RECEIPT_POLICY)
                self.assertTrue(any("cross-field" in error for error in errors), errors)

    def test_receipt_admission_rejects_duplicate_json_members(self) -> None:
        receipt = json.dumps(self.valid_receipt())
        duplicate = receipt[:-1] + ', "requested_effort": "max"}'

        result = self.admit_receipt(duplicate)

        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate JSON member: requested_effort", json.loads(result.stdout)["errors"])

    def test_receipt_admission_rejects_noncanonical_or_unbound_evidence(self) -> None:
        mutations = {
            "prompt echo": {
                "request_injection_evidence": {
                    **self.valid_receipt()["request_injection_evidence"],
                    "source_kind": "prompt_echo",
                }
            },
            "host default": {
                "request_injection_evidence": {
                    **self.valid_receipt()["request_injection_evidence"],
                    "source_kind": "host_default",
                }
            },
            "alias source": {
                "request_injection_evidence": {
                    **self.valid_receipt()["request_injection_evidence"],
                    "source_kind": "model_alias",
                }
            },
            "self attested source": {
                "request_injection_evidence": {
                    **self.valid_receipt()["request_injection_evidence"],
                    "source_kind": "self_attested",
                }
            },
            "mutated request digest": {
                "request_injection_evidence": {
                    **self.valid_receipt()["request_injection_evidence"],
                    "request_bytes_sha256": "0" * 64,
                }
            },
            "ambiguous provider": {"resolved_provider": "unknown"},
            "requested copied to readback": {
                "model_identity_basis": "independent_readback",
                "model_readback_evidence": {
                    "source_kind": "requested_value",
                    "status": "verified",
                    "schema": "runtime-assignment-readback/v1",
                },
            },
        }
        for name, changes in mutations.items():
            with self.subTest(mutation=name):
                receipt = self.valid_receipt()
                receipt.update(changes)
                result = self.admit_receipt(receipt)
                self.assertNotEqual(result.returncode, 0)
                denied = json.loads(result.stdout)
                self.assertEqual(denied["status"], "invalid")
                self.assertTrue(denied["errors"])

    def test_receipt_validation_rejects_closed_evidence_shapes_and_copied_readback(self) -> None:
        mutations = {
            "request extra": {
                "request_injection_evidence": {
                    **self.valid_receipt()["request_injection_evidence"],
                    "arbitrary_provenance": "caller says so",
                }
            },
            "model content-free": {
                "model_readback_evidence": {
                    "source_kind": "policy_exact_id_mapping",
                    "status": "unavailable",
                    "schema": "runtime-assignment-policy-v1",
                    "reference": "model-provider-map",
                    "model_id": "gpt-5.6-terra",
                }
            },
            "copied effort readback": {
                "effort_readback_status": "verified",
                "effort_readback_evidence": {
                    "source_kind": "transport_readback",
                    "status": "verified",
                    "schema": "runtime-assignment-readback/v1",
                    "observed_effort": "high",
                    "request_bytes_sha256": hashlib.sha256(
                        json.dumps(
                            {"context_form": "base", "effort": "high", "model_id": "gpt-5.6-terra"},
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                },
            },
        }
        for name, changes in mutations.items():
            with self.subTest(mutation=name):
                receipt = self.valid_receipt()
                receipt.update(changes)
                result = self.admit_receipt(receipt)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["status"], "invalid")

    def test_receipt_admission_rejects_uncertified_claude_context_tuple(self) -> None:
        receipt = self.valid_receipt()
        receipt.update(
            {
                "requested_model_id": "claude-opus-4-8",
                "requested_context_form": "[1m]",
                "resolved_provider": "anthropic",
                "resolved_model_id": "claude-opus-4-8",
            }
        )
        request = {"context_form": "[1m]", "effort": "high", "model_id": "claude-opus-4-8"}
        receipt["request_injection_evidence"] = {
            **receipt["request_injection_evidence"],
            "request_bytes_sha256": hashlib.sha256(
                json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
        }

        result = self.admit_receipt(receipt)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requested model/effort/context tuple is not certified", json.loads(result.stdout)["errors"])

    def test_receipt_admission_denies_unsafe_evidence_mutants(self) -> None:
        mutations = {
            "caller override": {"requested_model_id": "gpt-5.6-terra-override"},
            "contradictory fail closed": {"effort_readback_status": "verified"},
        }
        for name, changes in mutations.items():
            with self.subTest(mutation=name):
                receipt = self.valid_receipt()
                receipt.update(changes)
                result = self.admit_receipt(receipt)
                self.assertNotEqual(result.returncode, 0)
                denied = json.loads(result.stdout)
                self.assertEqual(denied["status"], "invalid")
                self.assertTrue(denied["errors"])


if __name__ == "__main__":
    unittest.main()
