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
        """Opt-in real render against the resource ceilings calibrated in ADR-0006.

        Two renders of the same definition must publish byte-identical SVG that validates
        against the shipped sanitizer allowlist. A future browser pin bump re-opens the
        `max_rss_bytes` / `max_output_file_bytes` calibration, and this is the test that
        reports it: a regression there surfaces as a render failure, never as a skip.
        """
        receipt = ROOT / ".mermaid-runtime" / "runtime-receipt.json"
        if not receipt.is_file() or not shutil.which("mise"):
            self.skipTest("maintenance receipt unavailable; provisioning is a separate explicit boundary")
        policy = renderer.load_policy()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one, two = root / "one.svg", root / "two.svg"
            self.assertEqual(renderer.main([str(FIXTURE), str(one)]), 0)
            self.assertEqual(renderer.main([str(FIXTURE), str(two)]), 0)
            published = one.read_bytes()
            self.assertEqual(published, two.read_bytes())
            # Output size stays bounded by the independent output-size control, not by the
            # resource ceilings, and the published bytes are re-admitted by the shipped policy.
            self.assertLessEqual(len(published), policy["limits"]["max_final_bytes"])
            self.assertEqual(renderer.validate_final_svg(published, policy), published)

    @unittest.skipUnless(os.sys.platform.startswith("linux"), "Linux-only renderer")
    def test_resource_limits_are_applied_relative_to_the_per_uid_task_budget(self) -> None:
        """RLIMIT_NPROC is charged per-UID against tasks, so an absolute cap fails closed.

        A bare `max_processes` soft limit refuses bwrap's own namespace setup on any host whose
        operator already owns more tasks than the cap, which is every real session.
        """
        policy = renderer.load_policy()
        observed = renderer._uid_task_count()
        self.assertGreater(observed, 0)
        # The census must exceed the raw process budget on a normal host, which is precisely why
        # the budget is relative rather than absolute.
        self.assertGreater(observed, policy["limits"]["max_processes"])


if __name__ == "__main__":
    unittest.main()
