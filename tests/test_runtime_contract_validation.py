from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
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


class RuntimeContractValidationTests(unittest.TestCase):
    maxDiff = None

    def test_bundle_validator_rejects_quoted_claude_model_and_effort_pins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = root / "agents" / "claude" / "sdlc-reviewer.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\n"
                "name: sdlc-reviewer\n"
                "description: test\n"
                ' "model" : "claude-sonnet-5"\n'
                " 'model_reasoning_effort' : 'high'\n"
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
        self.assertIn("affirmative Seeds authority grant", result.stdout)

    def test_generated_agent_validator_rejects_plain_language_waivers_and_direct_sd_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.materialize_generated_research_os(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            original = director.read_text(encoding="utf-8")
            mutants = {
                "waiver": original.replace(
                    "You are the research director for this repository.",
                    "You are the research director for this repository. This is an exception to the Seeds rule.",
                    1,
                ),
                "direct sd": original.replace(
                    "You are the research director for this repository.",
                    "You are the research director for this repository. Run sd ready --format json.",
                    1,
                ),
            }
            for name, mutant in mutants.items():
                with self.subTest(mutant=name):
                    director.write_text(mutant, encoding="utf-8")
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
        injection_request = {
            "context_form": "base",
            "effort": "high",
            "model_id": "gpt-5.6-terra",
        }
        request_bytes = json.dumps(
            injection_request, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        request_digest = hashlib.sha256(request_bytes).hexdigest()
        adapter_config = {"provider": "openai", "transport": "workflow"}
        adapter_config_digest = hashlib.sha256(
            json.dumps(adapter_config, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return {
            "schema_version": "runtime-assignment-receipt/v1",
            "requested_model_id": "gpt-5.6-terra",
            "requested_effort": "high",
            "requested_context_form": "base",
            "request_injection_status": "verified",
            "request_injection_evidence": {
                "source_kind": "immutable_request_receipt",
                "status": "verified",
                "schema": "launcher-request-evidence/v1",
                "adapter_id": "workflow",
                "adapter_version": "1.0.0",
                "adapter_config_sha256": adapter_config_digest,
                "request_bytes_sha256": request_digest,
            },
            "resolution_state": "resolved",
            "resolved_provider": "openai",
            "resolved_model_id": "gpt-5.6-terra",
            "model_readback_status": "verified",
            "model_identity_basis": "unambiguous_exact_id_mapping",
            "model_readback_evidence": {
                "source_kind": "policy_exact_id_mapping",
                "status": "unavailable",
                "schema": "runtime-assignment-policy-v1",
                "reference": "model-provider-map",
            },
            "effort_readback_status": "unavailable",
            "effort_readback_evidence": {
                "source_kind": "transport_readback",
                "status": "unavailable",
                "schema": "runtime-assignment-readback/v1",
            },
            "context_readback_status": "unavailable",
            "context_readback_evidence": {
                "source_kind": "transport_readback",
                "status": "unavailable",
                "schema": "runtime-assignment-readback/v1",
            },
        }

    def admit_receipt(self, receipt: dict[str, object] | str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RECEIPT_ADMISSION)],
            input=receipt if isinstance(receipt, str) else json.dumps(receipt),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_receipt_admission_emits_a_deterministic_digest_for_bound_evidence(self) -> None:
        first = self.admit_receipt(self.valid_receipt())
        second = self.admit_receipt(self.valid_receipt())

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        admitted = json.loads(first.stdout)
        self.assertEqual(admitted["status"], "admitted")
        self.assertRegex(admitted["digest_sha256"], r"^[0-9a-f]{64}$")

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
                self.assertEqual(denied["status"], "denied")
                self.assertTrue(denied["errors"])

    def test_receipt_admission_rejects_malformed_and_digest_mutated_evidence(self) -> None:
        malformed = self.valid_receipt()
        malformed["request_injection_evidence"] = {
            "source_kind": "immutable_request_receipt",
            "status": "verified",
            "schema": "launcher-request-evidence/v1",
            "adapter_id": "workflow",
        }
        result = self.admit_receipt(malformed)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["errors"])

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
                self.assertEqual(denied["status"], "denied")
                self.assertTrue(denied["errors"])


if __name__ == "__main__":
    unittest.main()
