from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "secrets_scan.py"


class SecretsScanTests(unittest.TestCase):
    def module(self) -> object:
        self.assertTrue(SCRIPT.is_file(), "the Git-aware secrets wrapper must exist")
        spec = importlib.util.spec_from_file_location("secrets_scan", SCRIPT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-c", "core.autocrlf=false", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def repository(self, temp: str) -> Path:
        root = Path(temp) / "repo"
        root.mkdir()
        self.git(root, "init", "--quiet")
        self.git(root, "config", "user.email", "test@example.invalid")
        self.git(root, "config", "user.name", "Secrets Scan Test")
        (root / ".gitignore").write_text(".gstack/\n", encoding="utf-8")
        config = root / ".config" / "betterleaks.toml"
        config.parent.mkdir()
        config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
        (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self.git(root, "add", ".gitignore", ".config/betterleaks.toml", "tracked.txt")
        self.git(root, "commit", "--quiet", "-m", "fixture")
        return root

    def test_git_visible_files_exclude_ignored_runtime_but_keep_tracked_and_untracked(self) -> None:
        module = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root = self.repository(temp)
            runtime = root / ".gstack" / "runtime.log"
            runtime.parent.mkdir()
            runtime.write_text("ignored runtime\n", encoding="utf-8")
            tracked_ignored = root / ".gstack" / "tracked.txt"
            tracked_ignored.write_text("force tracked\n", encoding="utf-8")
            self.git(root, "add", "-f", ".gstack/tracked.txt")
            (root / "ordinary untracked.txt").write_text("untracked\n", encoding="utf-8")

            paths = module.git_visible_files(root)

        self.assertIn(".gstack/tracked.txt", paths)
        self.assertIn("ordinary untracked.txt", paths)
        self.assertIn("tracked.txt", paths)
        self.assertNotIn(".gstack/runtime.log", paths)

    def test_git_visible_files_preserve_nul_delimited_path_names(self) -> None:
        module = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root = self.repository(temp)
            names = ("space name.txt", "unicodé.txt", "-leading-option.txt")
            for name in names:
                (root / name).write_text(name, encoding="utf-8")

            paths = module.git_visible_files(root)

        for name in names:
            self.assertIn(name, paths)

    @unittest.skipIf(os.name == "nt", "symlink creation needs developer mode on Windows")
    def test_git_visible_files_skip_symlinks_and_non_regular_entries(self) -> None:
        module = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root = self.repository(temp)
            (root / "regular.txt").write_text("regular\n", encoding="utf-8")
            (root / "linked.txt").symlink_to("regular.txt")

            paths = module.git_visible_files(root)

        self.assertIn("regular.txt", paths)
        self.assertNotIn("linked.txt", paths)

    def test_batches_keep_config_redaction_separator_and_byte_ceiling(self) -> None:
        module = self.module()
        prefix = [
            "/stub/betterleaks",
            "dir",
            "--redact=100",
            "--config",
            "/repo/.config/betterleaks.toml",
            "--",
        ]
        paths = [f"nested/{index:02d}-{'x' * 24}.txt" for index in range(12)]

        batches = module.batched_commands(prefix, paths, max_argv_bytes=180)

        self.assertGreater(len(batches), 1)
        flattened: list[str] = []
        for command in batches:
            self.assertEqual(command[: len(prefix)], prefix)
            self.assertLessEqual(module.argv_size(command), 180)
            flattened.extend(command[len(prefix) :])
        self.assertEqual(flattened, paths)

    def test_no_visible_files_do_not_resolve_or_invoke_scanner(self) -> None:
        module = self.module()
        with mock.patch.object(module.shutil, "which") as which, mock.patch.object(
            module, "run_scanner_batch"
        ) as run:
            code = module.scan_paths(Path("/repo"), [], Path("/repo/config.toml"))

        self.assertEqual(code, 0)
        which.assert_not_called()
        run.assert_not_called()

    def test_every_batch_uses_pinned_config_and_scanner_errors_outrank_findings(self) -> None:
        module = self.module()
        paths = [f"file-{index}-{'x' * 60}.txt" for index in range(10)]
        root = Path("/repo")
        config = root / ".config" / "betterleaks.toml"
        calls: list[list[str]] = []
        results = iter((1, 0, 7, 1, 0, 0, 0, 0, 0, 0))

        def run(command: list[str], cwd: Path) -> int:
            self.assertEqual(cwd, root)
            calls.append(command)
            return next(results)

        with mock.patch.object(module.shutil, "which", return_value="/stub/betterleaks"), mock.patch.object(
            module, "run_scanner_batch", side_effect=run
        ):
            code = module.scan_paths(root, paths, config, max_argv_bytes=180)

        self.assertEqual(code, 7)
        self.assertGreater(len(calls), 2)
        flattened: list[str] = []
        for command in calls:
            self.assertEqual(
                command[:6],
                [
                    "/stub/betterleaks",
                    "dir",
                    "--redact=100",
                    "--config",
                    str(config),
                    "--",
                ],
            )
            flattened.extend(command[6:])
        self.assertEqual(flattened, paths)

    def test_findings_exit_one_when_no_scanner_error_occurs(self) -> None:
        module = self.module()
        with mock.patch.object(module.shutil, "which", return_value="/stub/betterleaks"), mock.patch.object(
            module, "run_scanner_batch", side_effect=(0, 1)
        ):
            code = module.scan_paths(
                Path("/repo"),
                ["a" * 70, "b" * 70],
                Path("/repo/config.toml"),
                max_argv_bytes=160,
            )

        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
