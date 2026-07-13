from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MESSAGE = "CAO has been retired; use native Frame/Wave/Mission instead."
BASH = shutil.which("bash")


class CAORetirementTests(unittest.TestCase):
    def snapshot(self, root: Path) -> dict[str, str]:
        return {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }

    def run_script(self, repo: Path, script_name: str, *, env: dict[str, str], args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        script = repo / "scripts" / script_name
        command = [str(script), *(args or [])]
        if script.suffix == ".sh":
            if not BASH:
                self.skipTest("Bash is required for shell compatibility tests")
            command.insert(0, BASH)
        return subprocess.run(
            command,
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def copied_repo(self, temp: str) -> Path:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return repo

    def isolated_env(self, root: Path, bin_dir: Path, trace: Path, **extra: str) -> dict[str, str]:
        return os.environ | {
            "PATH": os.pathsep.join((str(bin_dir), os.environ["PATH"])),
            "TRACE": str(trace),
            "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_STATE_HOME": str(root / "xdg-state"),
            **extra,
        }

    def test_install_cao_kit_is_noop_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.copied_repo(temp)
            sandbox = root.parent / "sandbox"
            sandbox.mkdir()
            env = self.isolated_env(sandbox, root / "bin", sandbox / "trace")
            before_repo = self.snapshot(root)
            before_sandbox = self.snapshot(sandbox)
            result = self.run_script(root, "install-cao-kit.sh", env=env)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, MESSAGE + "\n")
            self.assertEqual(self.snapshot(root), before_repo)
            self.assertEqual(self.snapshot(sandbox), before_sandbox)

    def test_status_forwards_to_mise_but_retired_mode_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.copied_repo(temp)
            sandbox = root.parent / "sandbox"
            bin_dir = sandbox / "bin"
            bin_dir.mkdir(parents=True)
            mise = bin_dir / "mise"
            mise.write_text("#!/bin/sh\nprintf 'mise %s\\n' \"$*\" >> \"$TRACE\"\nexit 0\n")
            cao = bin_dir / "cao"
            cao.write_text("#!/bin/sh\nprintf 'cao %s\\n' \"$*\" >> \"$TRACE\"\nexit 99\n")
            mise.chmod(0o755)
            cao.chmod(0o755)
            trace = sandbox / "trace"
            env = self.isolated_env(sandbox, bin_dir, trace)
            before_repo = self.snapshot(root)
            ordinary = self.run_script(root, "install-skill-bundle.sh", env=env, args=["status"])
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertTrue(trace.exists(), ordinary.stderr)
            self.assertIn("run bundle:status", trace.read_text())
            self.assertNotIn("cao ", trace.read_text())
            after_ordinary = self.snapshot(root)
            retired = self.run_script(root, "install-skill-bundle.sh", env={**env, "INSTALL_CAO": "1"})
            self.assertEqual(retired.returncode, 2)
            self.assertEqual(retired.stdout, "")
            self.assertEqual(retired.stderr, MESSAGE + "\n")
            self.assertEqual(trace.read_text().count("mise "), 1)
            self.assertEqual(trace.read_text().count("cao "), 0)
            self.assertEqual(self.snapshot(root), after_ordinary)
            self.assertEqual(before_repo, after_ordinary)

    def test_retained_cao_surface_classes_are_tombstones(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.copied_repo(temp)
            paths = [root / "skills/agentic-sdlc-orchestrator/references/cao-profiles.md", root / "skills/agentic-sdlc-orchestrator/references/cao-operations.md", *sorted((root / "cao-profiles").glob("*"))]
            for path in paths:
                self.assertEqual(path.read_text(), MESSAGE + "\n", path)
    def assert_validator_rejects_active_cao_command(
        self, relative_path: str, command: str
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.copied_repo(temp)
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text() if target.exists() else ""
            target.write_text(existing + f"\n{command}\n")
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--python",
                    "3.12.11",
                    "--script",
                    str(root / "scripts" / "validate_bundle.py"),
                    "--root",
                    str(root),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            expected = (
                f"active INSTALL_CAO invocation remains: {relative_path}"
                if command.startswith("INSTALL_CAO=1")
                else f"active CAO command or claim remains: {relative_path}"
            )
            normalized_stderr = result.stderr.replace("\\", "/")
            self.assertIn(expected, normalized_stderr)

    def test_validator_rejects_active_cao_install_command(self) -> None:
        mutations = (
            ("README.md", "cao install arbitrary-profile"),
            ("mise.toml", "cao status"),
            ("lefthook.yml", "sudo cao doctor"),
            ("docs/guide.md", "$ cao status"),
            ("docs/guide.rst", "cao exec worker"),
            ("config/tool.ini", "command=cao-server start"),
            ("Makefile", "run:\n\tcao status"),
            ("README.md", "INSTALL_CAO=1 ./scripts/install-skill-bundle.sh"),
        )
        for relative_path, command in mutations:
            with self.subTest(path=relative_path, command=command):
                self.assert_validator_rejects_active_cao_command(relative_path, command)
    def test_validator_enforces_exact_profile_tombstone_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.copied_repo(temp)
            (root / "cao-profiles" / "codex-reviewer.md").unlink()
            result = subprocess.run(
                ["uv", "run", "--python", "3.12.11", "--script", str(root / "scripts/validate_bundle.py"), "--root", str(root)],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("CAO profile tombstone inventory mismatch", result.stderr)
    def test_validator_enforces_exact_cao_named_file_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.copied_repo(temp)
            rogue = root / "scripts" / "cao-helper.sh"
            rogue.write_text(MESSAGE + "\n")
            result = subprocess.run(
                ["uv", "run", "--python", "3.12.11", "--script", str(root / "scripts/validate_bundle.py"), "--root", str(root)],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("CAO named-file inventory mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
