from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scripts import gate_receipt


ROOT = Path(__file__).parents[1]
LOCK = ROOT / "mise.lock"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class GateReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.log_bytes = b"[check] validate/test/self-test all passed\n"
        cls.lock_bytes = LOCK.read_bytes()
        cls.receipt = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=0,
            log_bytes=cls.log_bytes,
            lock_bytes=cls.lock_bytes,
            cwd="/mnt/e/CS/github/agentic-sdlc-orchestrator-wt-g1g2-gates",
        )

    def test_receipt_is_canonical_and_self_verifying(self) -> None:
        # self_digest is sha256 of the canonical JSON of every OTHER field.
        others = {k: v for k, v in self.receipt.items() if k != "self_digest"}
        expected = _sha256_hex(
            json.dumps(others, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        )
        self.assertEqual(self.receipt["self_digest"], expected)
        self.assertTrue(gate_receipt.verify_receipt(self.receipt))
        # Canonical serialization round-trips byte-identically.
        canonical = gate_receipt.canonical_json(self.receipt)
        reparsed = json.loads(canonical.decode("utf-8"))
        self.assertEqual(gate_receipt.canonical_json(reparsed), canonical)

    def test_tampered_receipt_field_fails_self_digest(self) -> None:
        tampered = dict(self.receipt)
        tampered["status"] = 1  # mutate one field AFTER hashing
        self.assertNotEqual(
            gate_receipt.canonical_digest({k: v for k, v in tampered.items() if k != "self_digest"}),
            tampered["self_digest"],
        )
        self.assertFalse(gate_receipt.verify_receipt(tampered))

    def test_receipt_records_exact_argv_and_status_and_log_digest(self) -> None:
        self.assertEqual(self.receipt["gate"], "mise run check")
        self.assertEqual(self.receipt["argv"], ["mise", "run", "check"])
        self.assertIsInstance(self.receipt["status"], int)
        self.assertEqual(self.receipt["log_digest"], _sha256_hex(self.log_bytes))
        self.assertEqual(self.receipt["toolchain_digest"], _sha256_hex(self.lock_bytes))
        self.assertTrue(Path(self.receipt["cwd"]).is_absolute())

    def test_toolchain_digest_binds_lock(self) -> None:
        # The receipt's toolchain_digest matches the canonical lock it was built from...
        self.assertTrue(gate_receipt.verify_toolchain_binding(self.receipt, self.lock_bytes))
        # ...and a drifted lock (a single flipped byte) is flagged as a mismatch.
        drifted = self.lock_bytes.replace(b'version = "22.22.3"', b'version = "22.22.2"', 1)
        self.assertNotEqual(drifted, self.lock_bytes)
        self.assertFalse(gate_receipt.verify_toolchain_binding(self.receipt, drifted))


if __name__ == "__main__":
    unittest.main()
