from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ROADMAP = ROOT / "docs" / "roadmap"
SEEDS = ROOT / ".seeds" / "issues.jsonl"
EXPECTED_SEEDS_DIGEST = "0f239c6d0dbe14506b800cfc7ddb2a38cea030d1460e29c38ca2014606cf98e7"
INCIDENT_RECEIPT = ROADMAP / "trust-incident-and-seeds-provenance.md"


class RoadmapArchiveReceiptTests(unittest.TestCase):
    def test_incident_receipt_is_indexed_and_records_required_facts(self) -> None:
        self.assertTrue(INCIDENT_RECEIPT.is_file())
        self.assertIn(INCIDENT_RECEIPT.name, (ROADMAP / "index.md").read_text())
        receipt = INCIDENT_RECEIPT.read_text()
        self.assertIn(EXPECTED_SEEDS_DIGEST, receipt)
        self.assertIn("41 records, 5 epics, 36 work items", receipt)
        self.assertIn("96 directed dependency entries representing 48 relationships", receipt)
        for fact in (
            "untrusted",
            "persistent `mise trust`",
            "operation-specific user authorization",
            "trust-dependent gate subsequently passed",
            "later revoked",
            "custom or non-default locations were not exhaustively inspected",
            "does not retroactively authorize",
            "process-scoped `MISE_TRUSTED_CONFIG_PATHS` set only to the corrective worktree root",
            "user explicitly requested filing Seeds/epics/dependencies",
            "session conductor owns disposition",
            "delegated archive writer as the repository mutation actor",
            "separation of powers",
            "historical snapshot namespace, not final public product identity",
        ):
            with self.subTest(fact=fact):
                self.assertIn(fact, receipt)

    def test_canonical_seeds_graph_receipt_remains_exact(self) -> None:
        payload = SEEDS.read_bytes()
        issues = [json.loads(line) for line in payload.decode().splitlines() if line]
        self.assertEqual(EXPECTED_SEEDS_DIGEST, hashlib.sha256(payload).hexdigest())
        self.assertEqual(41, len(issues))
        self.assertEqual(5, sum(issue.get("type") == "epic" for issue in issues))
        self.assertEqual(36, sum(issue.get("type") != "epic" for issue in issues))
        directed_entries = sum(len(issue.get("blockedBy", [])) for issue in issues) + sum(
            len(issue.get("blocks", [])) for issue in issues
        )
        self.assertEqual(96, directed_entries)
        self.assertEqual(48, sum(len(issue.get("blocks", [])) for issue in issues))
        projection = (ROADMAP / "seeds-dependency-map.md").read_text()
        self.assertIn(EXPECTED_SEEDS_DIGEST, projection)

    def test_baseline_labels_historical_and_independent_receipts(self) -> None:
        baseline = (ROADMAP / "baseline-receipts.md").read_text()
        self.assertIn("historical plan statements, not current certification", baseline)
        self.assertIn("Git-clean", baseline)
        self.assertIn("Writer-reported gate", baseline)
        self.assertIn("independently rerun or certified", baseline)
        self.assertNotIn("| clean and gated |", baseline)
        self.assertNotIn("reports Git-clean and gated", baseline)


if __name__ == "__main__":
    unittest.main()
