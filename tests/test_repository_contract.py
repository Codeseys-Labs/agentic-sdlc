from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "agentic-sdlc" / "tools" / "repository-contract.py"


def _load():
    spec = importlib.util.spec_from_file_location("_agentic_sdlc_repository_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rc = _load()

VALID = """\
schema = "agentic-sdlc/repository-contract@1"
canonical_guidance = "AGENTS.md"
queue_adapter = "seeds"
adr_location = "docs/adr"
glossary_location = "CONTEXT.md"
authoritative_gate = "mise run check"
worktree_policy = "one writer per worktree"
integration_policy = "authorized serial fan-in"
ci_expectation = "calls the same pinned authoritative gate"
writing_profile = "evidence-preserving"
"""


class RepositoryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        self.state = self.target / ".agentic-sdlc"
        self.state.mkdir()
        self.path = self.state / "repo.toml"

    def write(self, body: str) -> Path:
        self.path.write_text(body, encoding="utf-8")
        return self.path

    def test_valid_contract_is_accepted_offline(self) -> None:
        self.write(VALID)

        result, code = rc.inspect_command(self.target)

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["contract"]["queue_adapter"], "seeds")

    def test_absent_contract_is_reported_not_invented(self) -> None:
        result, code = rc.inspect_command(self.target)

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "absent")
        self.assertIsNone(result["contract"])

    def assertRefused(self, result: dict, code: int, expected_code: int, fragment: str) -> None:
        """Assert WHICH check fired, not merely that something did. Without the reason,
        every refusal is an identical (refused, code) pair and no test can tell them
        apart -- which let several mutations survive."""
        self.assertEqual(result["status"], "refused", result)
        self.assertEqual(code, expected_code, result)
        self.assertTrue(
            any(fragment in reason for reason in result["reasons"]),
            f"expected a reason containing {fragment!r}, got {result['reasons']}",
        )

    def test_malformed_toml_is_refused(self) -> None:
        self.write('schema = "unterminated\n')

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 2, "malformed")

    def test_missing_required_field_is_refused(self) -> None:
        self.write(VALID.replace('queue_adapter = "seeds"\n', ""))

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 2, "missing")

    def test_unknown_field_is_refused(self) -> None:
        """Closed key set: an unrecognized field is a contract change, not a comment."""
        self.write(VALID + 'extra_thing = "surprise"\n')

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 2, "unknown")

    def test_empty_field_value_is_refused(self) -> None:
        self.write(VALID.replace('queue_adapter = "seeds"', 'queue_adapter = "   "'))

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 2, "queue_adapter")

    def test_unsupported_schema_is_refused(self) -> None:
        self.write(VALID.replace("repository-contract@1", "repository-contract@99"))

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 2, "unsupported contract schema")

    def test_ownership_or_readiness_claims_are_refused(self) -> None:
        """issues/09 and Implementation Decision 10: the manifest is not proof of
        ownership, tool, trust, route, or readiness. A manifest that claims any of
        those is refused rather than read and ignored."""
        for claim in (
            'readiness = "write-ready"',
            'ownership = "mine"',
            'trust_state = "trusted"',
            'route = "ocx"',
            'tool_versions = "pinned"',
        ):
            with self.subTest(claim=claim):
                self.write(VALID + claim + "\n")

                result, code = rc.inspect_command(self.target)

                self.assertEqual(result["status"], "refused", result)
                self.assertEqual(code, 2)

    def test_result_never_asserts_readiness(self) -> None:
        self.write(VALID)

        result, _ = rc.inspect_command(self.target)

        for forbidden in ("readiness", "ownership", "trust", "approved", "authorized"):
            self.assertNotIn(forbidden, result, f"result must not assert {forbidden}")

    def test_symlinked_contract_is_refused(self) -> None:
        decoy = self.target / "decoy.toml"
        decoy.write_text(VALID, encoding="utf-8")
        self.path.symlink_to(decoy)

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 3, "repo.toml")

    def test_symlinked_state_directory_is_refused(self) -> None:
        """A symlinked PARENT redirected custody outside the repository entirely and was
        reported as a valid contract, because only the final component was checked."""
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "repo.toml").write_text(
            VALID.replace('queue_adapter = "seeds"', 'queue_adapter = "ATTACKER"'), encoding="utf-8"
        )
        for path in sorted(self.state.iterdir()):
            path.unlink()
        self.state.rmdir()
        self.state.symlink_to(outside)

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 3, ".agentic-sdlc")
        self.assertIsNone(result["contract"])

    def test_unreadable_state_directory_is_not_reported_absent(self) -> None:
        """Reporting an unreadable manifest as `absent` tells the caller there is no
        portable intent when there is one it cannot read."""
        self.write(VALID)
        os.chmod(self.state, 0o000)
        self.addCleanup(os.chmod, self.state, 0o755)

        result, code = rc.inspect_command(self.target)

        if result["status"] == "valid":
            self.skipTest("running with privileges that bypass directory permissions")
        self.assertRefused(result, code, 3, ".agentic-sdlc")

    def test_fifo_contract_is_refused_without_blocking(self) -> None:
        os.mkfifo(self.path)

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 3, "regular file")

    def test_non_utf8_contract_is_refused(self) -> None:
        self.path.write_bytes(b'schema = "\xff\xfe"\n')

        result, code = rc.inspect_command(self.target)

        self.assertRefused(result, code, 2, "not UTF-8")

    def test_inspection_writes_nothing(self) -> None:
        self.write(VALID)
        before = {
            path: path.stat().st_mtime_ns
            for path in sorted(self.target.rglob("*"))
        }

        rc.inspect_command(self.target)

        after = {
            path: path.stat().st_mtime_ns
            for path in sorted(self.target.rglob("*"))
        }
        self.assertEqual(before, after)

    def test_inspection_is_deterministic(self) -> None:
        self.write(VALID)

        first, _ = rc.inspect_command(self.target)
        second, _ = rc.inspect_command(self.target)

        self.assertEqual(first, second)

    def test_relative_target_is_refused(self) -> None:
        """Matches the activation engine: absolute Linux paths only."""
        result, code = rc.inspect_command(Path("relative/path"))

        self.assertEqual(result["status"], "refused")
        self.assertNotEqual(code, 0)

    def test_cli_emits_canonical_json_and_returns_the_code(self) -> None:
        self.write(VALID)
        import subprocess

        done = subprocess.run(
            [sys.executable, str(SCRIPT), "inspect", "--target", str(self.target)],
            capture_output=True,
            check=False,
        )

        self.assertEqual(done.returncode, 0, done.stderr.decode())
        self.assertTrue(done.stdout.endswith(b"\n"))
        self.assertEqual(rc.canonical_bytes(rc.json.loads(done.stdout)), done.stdout)


if __name__ == "__main__":
    unittest.main()
