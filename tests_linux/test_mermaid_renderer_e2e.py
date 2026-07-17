from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import render_mermaid_linux as renderer


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "mermaid-renderer" / "trusted-flowchart.mmd"


@unittest.skipIf(os.name == "nt", "Linux-only M0b egress boundary is not certified on native Windows")
class MermaidRendererLinuxE2ETests(unittest.TestCase):
    def test_non_linux_wrapper_fails_closed_as_unsupported(self) -> None:
        if os.sys.platform.startswith("linux"):
            self.skipTest("covered by required Linux capability and real-render tests")
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "result.svg"
            self.assertEqual(renderer.main([str(FIXTURE), str(destination)]), renderer.EXIT_UNSUPPORTED)
            self.assertFalse(destination.exists())

    @unittest.skipUnless(os.sys.platform.startswith("linux"), "Linux-only renderer")
    def test_linux_requires_bwrap_before_rendering(self) -> None:
        if not Path("/usr/bin/bwrap").is_file():
            self.skipTest("required Linux bwrap capability is unavailable")
        self.assertTrue(os.access("/usr/bin/bwrap", os.X_OK))

    @unittest.skipUnless(
        os.sys.platform.startswith("linux") and os.environ.get("MERMAID_M0B_E2E") == "1",
        "set MERMAID_M0B_E2E=1 only on a Linux host that permits required bwrap namespaces",
    )
    def test_real_pinned_render_is_deterministic_when_runtime_is_provisioned(self) -> None:
        receipt = ROOT / ".mermaid-runtime" / "runtime-receipt.json"
        if not receipt.is_file() or not shutil.which("mise"):
            self.skipTest("maintenance receipt unavailable; provisioning is a separate explicit boundary")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one, two = root / "one.svg", root / "two.svg"
            self.assertEqual(renderer.main([str(FIXTURE), str(one)]), 0)
            self.assertEqual(renderer.main([str(FIXTURE), str(two)]), 0)
            self.assertEqual(one.read_bytes(), two.read_bytes())


if __name__ == "__main__":
    unittest.main()
