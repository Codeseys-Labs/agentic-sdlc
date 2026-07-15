from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).parents[1]
BUNDLE_VALIDATOR = ROOT / "scripts" / "validate_bundle.py"
RESEARCH_INSTALLER = ROOT / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
RECEIPT_ADMISSION = ROOT / "skills" / "model-tier-rightsizing" / "scripts" / "receipt_admission.py"


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

    def test_bundle_validator_enforces_policy_derived_runtime_projection_for_all_role_types(self) -> None:
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

    def test_generated_agent_validator_rejects_director_launcher_and_seed_authority_mutants(self) -> None:
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
