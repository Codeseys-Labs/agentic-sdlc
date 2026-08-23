from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "cmux-bus.sh"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "Bash is required for cmux-bus.sh tests")
class CmuxBusExitCodeTests(unittest.TestCase):
    """decision9-conformance-survey SP-5: an absent `cmux` CLI and a "not inside cmux"
    state must both be named clean refusals (3), never 1 and never a silent 0; the
    `cmux log` exit code that backs `pub` is translated to a single named code (6) rather
    than mirrored, so it can never collide with this wrapper's own clean-refusal 3."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin_with_cmux = self.root / "bin-with-cmux"
        self.bin_with_cmux.mkdir()
        self.bin_without_cmux = self.root / "bin-without-cmux"
        self.bin_without_cmux.mkdir()
        self.cmux_log_calls = self.root / "cmux-log-calls.jsonl"

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _write_stub_cmux(self, *, log_exit: int) -> Path:
        stub = self.bin_with_cmux / "cmux"
        self._write_executable(
            stub,
            "#!/bin/sh\n"
            f'if [ "$1" = "log" ]; then\n'
            f'  printf \'%s\\n\' "$*" >> "{self.cmux_log_calls}"\n'
            f"  exit {log_exit}\n"
            "fi\n"
            "exit 0\n",
        )
        return stub

    def environment_without_cmux(self, **overrides: str) -> dict[str, str]:
        return os.environ | {
            "PATH": str(self.bin_without_cmux) + os.pathsep + os.defpath,
            "CMUX_WORKSPACE_ID": "",
            **overrides,
        }

    def environment_with_cmux(self, **overrides: str) -> dict[str, str]:
        return os.environ | {
            "PATH": str(self.bin_with_cmux) + os.pathsep + os.defpath,
            **overrides,
        }

    def run_bus(self, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(SCRIPT), *args],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    # -- absent dependency: negative + positive control ---------------------------------

    def test_absent_cmux_is_a_named_refusal_not_an_internal_failure(self) -> None:
        result = self.run_bus("pub", "topic", "message", env=self.environment_without_cmux())
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertNotEqual(result.returncode, 1)
        self.assertIn("cmux CLI not on PATH", result.stderr)

    def test_present_cmux_does_not_trip_the_absent_dependency_refusal(self) -> None:
        # Positive control: the same command with cmux ON PATH (and inside cmux) does not
        # take the "absent dependency" branch at all.
        self._write_stub_cmux(log_exit=0)
        result = self.run_bus(
            "pub",
            "topic",
            "message",
            env=self.environment_with_cmux(CMUX_WORKSPACE_ID="ws-1"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("cmux CLI not on PATH", result.stderr)

    # -- not-inside-cmux: negative + positive control ------------------------------------

    def test_not_inside_cmux_is_a_named_refusal_not_a_silent_success(self) -> None:
        self._write_stub_cmux(log_exit=0)
        result = self.run_bus(
            "pub",
            "topic",
            "message",
            env=self.environment_with_cmux(CMUX_WORKSPACE_ID=""),
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not inside cmux", result.stderr)
        self.assertFalse(self.cmux_log_calls.exists(), "no publish may occur outside cmux")

    def test_inside_cmux_with_workspace_id_set_does_not_trip_the_refusal(self) -> None:
        # Positive control: setting CMUX_WORKSPACE_ID is the one thing that distinguishes
        # the refused state from the accepted one; everything else stays identical.
        self._write_stub_cmux(log_exit=0)
        result = self.run_bus(
            "pub",
            "topic",
            "message",
            env=self.environment_with_cmux(CMUX_WORKSPACE_ID="ws-1"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("not inside cmux", result.stderr)
        self.assertTrue(self.cmux_log_calls.exists())

    # -- cmux log failure is translated to one named code, never mirrored --------------

    def test_cmux_log_failure_is_translated_to_the_named_publish_failed_code(self) -> None:
        # Any nonzero `cmux log` exit -- including one that happens to collide with this
        # wrapper's OWN clean-refusal code (3) -- comes out as the single named 6, never
        # passed through raw. 1/2/3/7 stand in for "any nonzero status this arbitrary
        # external CLI could return".
        for child_exit in (1, 2, 3, 7):
            with self.subTest(child_exit=child_exit):
                self._write_stub_cmux(log_exit=child_exit)
                result = self.run_bus(
                    "pub",
                    "topic",
                    "message",
                    env=self.environment_with_cmux(CMUX_WORKSPACE_ID="ws-1"),
                )
                self.assertEqual(result.returncode, 6, result.stderr)
                self.assertIn("cmux log failed", result.stderr)

    def test_cmux_log_success_still_exits_zero(self) -> None:
        # Positive control: translation only fires on FAILURE -- a successful `cmux log`
        # (0) is not rewritten to some other constant.
        self._write_stub_cmux(log_exit=0)
        result = self.run_bus(
            "pub",
            "topic",
            "message",
            env=self.environment_with_cmux(CMUX_WORKSPACE_ID="ws-1"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("cmux log failed", result.stderr)

    # -- help stays a 0-class query, now reachable even without cmux --------------------

    def test_help_is_reachable_and_zero_even_without_cmux(self) -> None:
        result = self.run_bus("--help", env=self.environment_without_cmux())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("USAGE", result.stdout)

    def test_help_prints_the_full_exit_table_including_its_last_line(self) -> None:
        # The header's `sed` range must cover the WHOLE header, not just its older, shorter
        # prefix -- assert a line from the END of the exit table (not merely its first "0"
        # row) actually reaches stdout, so a range that silently truncates the table again
        # is caught here rather than by eyeballing --help output.
        result = self.run_bus("--help", env=self.environment_without_cmux())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("decision9 survey's SP-5 REMEDIATION", result.stdout)

    def test_no_mode_is_also_the_help_query(self) -> None:
        result = self.run_bus(env=self.environment_without_cmux())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("USAGE", result.stdout)

    # -- grammar codes the survey said were already correct: untouched ------------------

    def test_unknown_mode_is_still_a_grammar_error(self) -> None:
        self._write_stub_cmux(log_exit=0)
        result = self.run_bus(
            "not-a-real-mode",
            env=self.environment_with_cmux(CMUX_WORKSPACE_ID="ws-1"),
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("unknown mode", result.stderr)

    def test_pub_missing_topic_is_still_a_grammar_error(self) -> None:
        self._write_stub_cmux(log_exit=0)
        result = self.run_bus(
            "pub",
            env=self.environment_with_cmux(CMUX_WORKSPACE_ID="ws-1"),
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("need a topic", result.stderr)


if __name__ == "__main__":
    unittest.main()
