from __future__ import annotations

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
                'model: "claude-sonnet-5"\n'
                "model_reasoning_effort: 'high'\n"
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

    def valid_receipt(self) -> dict[str, str]:
        return {
            "schema_version": "runtime-assignment-receipt/v1",
            "requested_model_id": "gpt-5.6-terra",
            "requested_effort": "high",
            "requested_context_form": "base",
            "request_injection_status": "verified",
            "request_injection_source": "launcher.request.v1",
            "request_injection_evidence": "immutable-request:sha256:abc",
            "resolution_state": "resolved",
            "resolved_provider": "openai",
            "resolved_model_id": "gpt-5.6-terra",
            "model_readback_status": "verified",
            "model_identity_basis": "unambiguous_exact_id_mapping",
            "model_readback_source": "unavailable_in_transport",
            "model_readback_evidence": "policy:runtime-assignment-policy-v1#model-provider-map",
            "effort_readback_status": "unavailable",
            "effort_readback_source": "unavailable_in_transport",
            "effort_readback_evidence": "unavailable_in_transport",
            "context_readback_status": "unavailable",
            "context_readback_source": "unavailable_in_transport",
            "context_readback_evidence": "unavailable_in_transport",
        }

    def admit_receipt(self, receipt: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RECEIPT_ADMISSION)],
            input=json.dumps(receipt),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_receipt_admission_emits_a_deterministic_digest_for_valid_evidence(self) -> None:
        first = self.admit_receipt(self.valid_receipt())
        second = self.admit_receipt(self.valid_receipt())

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        admitted = json.loads(first.stdout)
        self.assertEqual(admitted["status"], "admitted")
        self.assertRegex(admitted["digest_sha256"], r"^[0-9a-f]{64}$")

    def test_receipt_admission_denies_unsafe_evidence_mutants(self) -> None:
        mutations = {
            "host default": {"request_injection_source": "host_default"},
            "caller override": {"requested_model_id": "gpt-5.6-terra-override"},
            "requested copied to readback": {
                "model_identity_basis": "independent_readback",
                "model_readback_source": "requested_model_id",
            },
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
