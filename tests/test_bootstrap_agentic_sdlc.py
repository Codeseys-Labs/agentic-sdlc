from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "bootstrap-agentic-sdlc.sh"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "Bash is required for bootstrap script tests")
class BootstrapAgenticSdlcTests(unittest.TestCase):
    def run_script(self, *args: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )

    def test_help_explains_explicit_remote_and_has_no_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed = root / "managed"
            state = root / "state"
            result = self.run_script(
                "--help",
                environment=os.environ | {
                    "AGENTIC_SDLC_HOME": str(managed),
                    "XDG_STATE_HOME": str(state),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--remote <git-url>", result.stdout)
            self.assertIn("--ref <ref>", result.stdout)
            self.assertIn("--dry-run and --print-path write nothing", result.stdout)
            self.assertFalse(managed.exists())
            self.assertFalse(state.exists())

    def test_print_path_needs_no_tools_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed = root / "managed"
            result = self.run_script(
                "--print-path",
                environment=os.environ | {
                    "AGENTIC_SDLC_HOME": str(managed),
                    "XDG_STATE_HOME": str(root / "state"),
                    "PATH": "",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(managed))
            self.assertFalse(managed.exists())

    def test_dry_run_reports_explicit_remote_without_creating_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for name in ("git", "mise"):
                tool = bin_dir / name
                tool.write_text("#!/bin/sh\nexit 0\n")
                tool.chmod(0o755)
            managed = root / "managed"
            state = root / "state"
            remote = "https://example.test/agentic-sdlc.git"
            result = self.run_script(
                "--dry-run",
                "--remote",
                remote,
                "--ref",
                "release-test",
                environment=os.environ | {
                    "PATH": str(bin_dir) + os.pathsep + os.defpath,
                    "AGENTIC_SDLC_HOME": str(managed),
                    "XDG_STATE_HOME": str(state),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"remote        : {remote}", result.stdout)
            self.assertIn("ref           : release-test", result.stdout)
            self.assertIn(f"git clone --depth 1 --branch release-test {remote} {managed}", result.stdout)
            self.assertFalse(managed.exists())
            self.assertFalse(state.exists())

    def test_completed_fetch_prints_verification_and_first_use_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            git = bin_dir / "git"
            git.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = clone ]; then\n"
                "  for target do :; done\n"
                "  mkdir -p \"$target/.git\"\n"
                "  exit 0\n"
                "fi\n"
                "if [ \"$1\" = -C ]; then\n"
                "  case \"$3\" in\n"
                "    rev-parse) printf '%s\\n' 0123456789abcdef ;;\n"
                "  esac\n"
                "fi\n"
            )
            git.chmod(0o755)
            mise = bin_dir / "mise"
            mise.write_text("#!/bin/sh\nprintf '%s\\n' untrusted\n")
            mise.chmod(0o755)
            managed = root / "managed"
            state = root / "state"
            result = self.run_script(
                "--remote",
                "https://example.test/agentic-sdlc.git",
                environment=os.environ | {
                    "PATH": str(bin_dir) + os.pathsep + os.defpath,
                    "AGENTIC_SDLC_HOME": str(managed),
                    "XDG_STATE_HOME": str(state),
                },
            )

            receipt = state / "agentic-sdlc" / "bootstrap-receipt.json"
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(receipt.is_file())
            self.assertIn("Verify this managed fetch before first use:", result.stdout)
            self.assertIn(f"remote/commit receipt: {receipt}", result.stdout)
            self.assertIn("First-use handoff, each command needs its own approval", result.stdout)
            self.assertIn("bundle:install -- --agent claude", result.stdout)
            self.assertIn("bundle:install -- --agent codex", result.stdout)
            self.assertIn("run bundle:status", result.stdout)

    @unittest.skipUnless(shutil.which("git"), "Git is required for real bootstrap update tests")
    def test_shallow_managed_clone_fast_forwards_after_remote_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            remote = root / "remote.git"
            managed = root / "managed"
            state = root / "state"
            bin_dir = root / "bin"
            bin_dir.mkdir()
            mise = bin_dir / "mise"
            mise.write_text("#!/bin/sh\nprintf '%s\\n' untrusted\n")
            mise.chmod(0o755)

            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            source.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=source, check=True)
            tracked = source / "tracked.txt"
            tracked.write_text("A\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "A"], cwd=source, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=source, check=True)
            subprocess.run(["git", "push", "-q", "-u", "origin", "main"], cwd=source, check=True)
            first = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=True
            ).stdout.strip()
            environment = os.environ | {
                "PATH": str(bin_dir) + os.pathsep + os.defpath,
                "AGENTIC_SDLC_HOME": str(managed),
                "XDG_STATE_HOME": str(state),
            }
            remote_url = remote.as_uri()

            bootstrapped = self.run_script("--remote", remote_url, environment=environment)
            self.assertEqual(bootstrapped.returncode, 0, bootstrapped.stderr)
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=managed, text=True, capture_output=True, check=True
                ).stdout.strip(),
                first,
            )

            tracked.write_text("B\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-qam", "B"], cwd=source, check=True)
            subprocess.run(["git", "push", "-q", "origin", "main"], cwd=source, check=True)
            second = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=True
            ).stdout.strip()

            updated = self.run_script(
                "--update", "--remote", remote_url, environment=environment
            )

            self.assertEqual(updated.returncode, 0, updated.stderr)
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=managed, text=True, capture_output=True, check=True
                ).stdout.strip(),
                second,
            )
            receipt = json.loads(
                (state / "agentic-sdlc" / "bootstrap-receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["commit"], second)

    def test_receipt_json_escapes_remote_ref_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            git = bin_dir / "git"
            git.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = clone ]; then for target do :; done; mkdir -p \"$target/.git\"; exit 0; fi\n"
                "if [ \"$1\" = -C ] && [ \"$3\" = rev-parse ]; then printf '%s\\n' 0123456789abcdef; fi\n"
            )
            git.chmod(0o755)
            mise = bin_dir / "mise"
            mise.write_text("#!/bin/sh\nprintf '%s\\n' untrusted\n")
            mise.chmod(0o755)
            managed = root / 'managed "checkout"'
            state = root / "state"
            remote = 'https://example.test/a"b.git'
            reference = 'release"candidate'

            result = self.run_script(
                "--remote",
                remote,
                "--ref",
                reference,
                environment=os.environ | {
                    "PATH": str(bin_dir) + os.pathsep + os.defpath,
                    "AGENTIC_SDLC_HOME": str(managed),
                    "XDG_STATE_HOME": str(state),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((state / "agentic-sdlc" / "bootstrap-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["remote"], remote)
            self.assertEqual(receipt["ref"], reference)
            self.assertEqual(receipt["path"], str(managed))

    def test_non_https_remote_does_not_claim_https_authentication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            git = bin_dir / "git"
            git.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = clone ]; then for target do :; done; mkdir -p \"$target/.git\"; exit 0; fi\n"
                "if [ \"$1\" = -C ] && [ \"$3\" = rev-parse ]; then printf '%s\\n' 0123456789abcdef; fi\n"
            )
            git.chmod(0o755)
            mise = bin_dir / "mise"
            mise.write_text("#!/bin/sh\nprintf '%s\\n' untrusted\n")
            mise.chmod(0o755)

            result = self.run_script(
                "--remote",
                "file:///reviewed/agentic-sdlc.git",
                environment=os.environ | {
                    "PATH": str(bin_dir) + os.pathsep + os.defpath,
                    "AGENTIC_SDLC_HOME": str(root / "managed"),
                    "XDG_STATE_HOME": str(root / "state"),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Transport was authenticated by HTTPS", result.stdout)
            self.assertIn("does not establish HTTPS authentication", result.stdout)


if __name__ == "__main__":
    unittest.main()
