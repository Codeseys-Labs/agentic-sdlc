from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import validate_bundle


ROOT = Path(__file__).parents[1]
POLICY = ROOT / "policy" / "mermaid-renderer-linux-v1.json"
PACKAGE = ROOT / "package.json"
LOCK = ROOT / "package-lock.json"


class MermaidRendererGateTests(unittest.TestCase):
    def test_exact_renderer_supply_chain_and_policy_contract(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(package["private"], True)
        self.assertEqual(
            package["dependencies"],
            {
                "@mermaid-js/mermaid-cli": "11.16.0",
                "@puppeteer/browsers": "3.0.6",
                "mermaid": "11.16.0",
                "puppeteer": "25.3.0",
            },
        )
        self.assertEqual(hashlib.sha256(LOCK.read_bytes()).hexdigest(), validate_bundle.MERMAID_PACKAGE_LOCK_SHA256)
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["schema_version"], "mermaid-renderer-linux/v1")
        self.assertEqual(policy["browser"]["build_id"], "150.0.7871.24")
        self.assertEqual(policy["browser"]["executable_sha256"], "db4fe5b63d1b56729feb1eeebc82967768e66ef823ba942b2d4e506a34dc4a78")
        self.assertEqual(policy["browser"]["cache_tree_sha256"], "3afbf64662eb240f67e98b7f352532de67e09dc9dabfd5390172c0c630b7ecfa")

    def test_validator_rejects_renderer_policy_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            import shutil
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "node_modules", ".mermaid-runtime", "__pycache__"))
            policy = root / POLICY.relative_to(ROOT)
            document = json.loads(policy.read_text(encoding="utf-8"))
            document["limits"]["max_final_bytes"] += 1
            policy.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            result = validate_bundle.validate(root)
        self.assertIn("Mermaid renderer policy does not match the canonical contract", result.errors)


if __name__ == "__main__":
    unittest.main()
