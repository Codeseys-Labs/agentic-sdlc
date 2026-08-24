from __future__ import annotations

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
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

    @unittest.skipIf(os.name == "nt", "symlink creation needs developer mode on Windows")
    def test_git_visible_files_skip_files_below_symlinked_directories(self) -> None:
        module = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root = self.repository(temp)
            outside = Path(temp) / "outside"
            outside.mkdir()
            (outside / "tracked.txt").write_text("outside\n", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "tracked.txt").write_text("inside\n", encoding="utf-8")
            self.git(root, "add", "nested/tracked.txt")
            self.git(root, "commit", "--quiet", "-m", "nested fixture")
            shutil.rmtree(root / "nested")
            (root / "nested").symlink_to(outside, target_is_directory=True)

            paths = module.git_visible_files(root)

        self.assertNotIn("nested/tracked.txt", paths)

    def test_git_visible_files_checks_link_type_before_file_type(self) -> None:
        module = self.module()
        calls: list[str] = []

        class Candidate:
            def is_symlink(self) -> bool:
                calls.append("is_symlink")
                return True

            def is_file(self) -> bool:
                calls.append("is_file")
                raise AssertionError("a symlink must not be followed")

        class Root:
            def __truediv__(self, _relative: str) -> Candidate:
                return Candidate()

            def __str__(self) -> str:
                return "/repo"

        completed = subprocess.CompletedProcess([], 0, b"linked.txt\0", b"")
        with mock.patch.object(module.subprocess, "run", return_value=completed):
            paths = module.git_visible_files(Root())

        self.assertEqual(paths, [])
        self.assertEqual(calls, ["is_symlink"])

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

    def test_help_exits_zero_and_does_not_enumerate_or_scan(self) -> None:
        module = self.module()
        with mock.patch.object(
            module, "git_visible_files", side_effect=AssertionError("--help must not scan")
        ) as sentinel:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    module.main(["--help"])

        self.assertEqual(ctx.exception.code, module.EXIT_OK)
        # The usage line must actually reach stdout: a `print_help` that emitted nothing would
        # otherwise pass on the exit code alone.
        self.assertIn("usage: secrets_scan.py", buffer.getvalue())
        sentinel.assert_not_called()

    def test_unknown_flag_exits_two_before_enumerating_or_scanning(self) -> None:
        module = self.module()
        with mock.patch.object(
            module, "git_visible_files", side_effect=AssertionError("--zzz must not scan")
        ) as sentinel:
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    module.main(["--zzz-not-a-flag"])

        self.assertEqual(ctx.exception.code, module.EXIT_USAGE)
        self.assertIn("unrecognized arguments", buffer.getvalue())
        sentinel.assert_not_called()

    def test_argv_none_dispatch_reads_the_real_sys_argv(self) -> None:
        # `main()` is what `if __name__ == "__main__"` calls, with no argument at all, so the
        # `argv is None` path must reach argparse through the real `sys.argv`. Every other test
        # here passes an explicit list and would still pass if that path were broken.
        module = self.module()
        with mock.patch.object(sys, "argv", ["secrets_scan.py", "--zzz-not-a-flag"]):
            with mock.patch.object(
                module, "git_visible_files", side_effect=AssertionError("sys.argv must be parsed")
            ) as refused:
                buffer = io.StringIO()
                with contextlib.redirect_stderr(buffer):
                    with self.assertRaises(SystemExit) as ctx:
                        module.main()

        self.assertEqual(ctx.exception.code, module.EXIT_USAGE)
        self.assertIn("unrecognized arguments", buffer.getvalue())
        refused.assert_not_called()

        # Positive control on the same `argv is None` path: a bare real `sys.argv` scans.
        with mock.patch.object(sys, "argv", ["secrets_scan.py"]):
            with mock.patch.object(module, "git_visible_files", return_value=[]) as reached:
                code = module.main()

        reached.assert_called_once()
        self.assertEqual(code, module.EXIT_OK)

    def test_no_arguments_still_reaches_the_real_scan_entry_point(self) -> None:
        # Positive control for the two tests above: a bare invocation (the mise secrets task's
        # exact shape) must still reach the enumeration step, so "nothing happened" above is not
        # vacuously true because the seam is never called at all.
        module = self.module()
        with mock.patch.object(module, "git_visible_files", return_value=[]) as sentinel:
            code = module.main([])

        sentinel.assert_called_once()
        self.assertEqual(code, 0)

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


class SecretsScanExitSplitTests(unittest.TestCase):
    """SP-3's third clause for this surface: a refusal reached before any file is scanned is
    EXIT_PRECONDITION (3), so it can no longer be mistaken for argparse's 2, while the scan's own
    codes -- 0, a found leak's 1, and a passed-through scanner code -- are unchanged, because
    `mise run check` reads them.
    """

    # The module loader is borrowed rather than inherited: subclassing the suite above would
    # re-run every one of its tests a second time under this class's name.
    module = SecretsScanTests.module

    def assert_precondition(self, error: BaseException, module: object) -> None:
        self.assertIsInstance(error, module.SecretsScanError)
        self.assertIn(str(error), module.PRECONDITION_REASONS)
        self.assertEqual(module.refusal_exit_code(error), module.EXIT_PRECONDITION)
        self.assertEqual(module.EXIT_PRECONDITION, 3)

    def test_missing_pinned_config_is_a_precondition_refusal_at_three(self) -> None:
        module = self.module()
        with mock.patch.object(module, "CONFIG_PATH", Path("no-such-dir/betterleaks.toml")):
            with mock.patch.object(
                module, "git_visible_files", side_effect=AssertionError("must not enumerate")
            ) as sentinel:
                with self.assertRaises(module.SecretsScanError) as ctx:
                    module.main([])

        self.assertEqual(str(ctx.exception), "pinned-secrets-config-missing")
        self.assert_precondition(ctx.exception, module)
        sentinel.assert_not_called()

    def test_failed_git_enumeration_is_a_precondition_refusal_at_three(self) -> None:
        module = self.module()
        failed = subprocess.CompletedProcess([], 1, b"", b"fatal: not a git repository")
        with mock.patch.object(module.subprocess, "run", return_value=failed):
            with mock.patch.object(
                module, "scan_paths", side_effect=AssertionError("must not scan")
            ) as sentinel:
                with self.assertRaises(module.SecretsScanError) as ctx:
                    module.main([])

        self.assertEqual(str(ctx.exception), "git-visible-file-enumeration-failed")
        self.assert_precondition(ctx.exception, module)
        sentinel.assert_not_called()

    def test_absent_betterleaks_is_a_precondition_refusal_at_three(self) -> None:
        module = self.module()
        with mock.patch.object(module, "git_visible_files", return_value=["tracked.txt"]):
            with mock.patch.object(module.shutil, "which", return_value=None):
                with mock.patch.object(
                    module, "run_scanner_batch", side_effect=AssertionError("no scanner to run")
                ) as sentinel:
                    with self.assertRaises(module.SecretsScanError) as ctx:
                        module.main([])

        self.assertEqual(str(ctx.exception), "betterleaks-not-found")
        self.assert_precondition(ctx.exception, module)
        sentinel.assert_not_called()

    def test_an_oversized_path_stays_an_input_class_two_not_a_precondition(self) -> None:
        # Negative control for the three tests above: the mapping is a named set, not "every
        # SecretsScanError is now 3". An enumerated path that cannot fit the scanner's argv is an
        # unusable input, which Decision 9 puts at 2.
        module = self.module()
        error = module.SecretsScanError("path-exceeds-scanner-argv-limit")

        self.assertNotIn(str(error), module.PRECONDITION_REASONS)
        self.assertEqual(module.refusal_exit_code(error), module.EXIT_USAGE)
        self.assertEqual(module.EXIT_USAGE, 2)

    def test_the_missing_config_refusal_exits_three_end_to_end(self) -> None:
        # The `__main__` block is the only place `refusal_exit_code` is consumed, and no
        # in-process test can reach it. Run a copy of the real script in a tree with no pinned
        # config so the whole path -- raise, message, exit -- is observed from outside.
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "scripts" / "secrets_scan.py"
            copy.parent.mkdir()
            copy.write_bytes(SCRIPT.read_bytes())
            completed = subprocess.run(
                [sys.executable, "-B", str(copy)],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 3, completed.stderr)
        self.assertIn("error: pinned-secrets-config-missing", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_a_found_leak_still_exits_one_because_the_gate_reads_that_code(self) -> None:
        # Positive control for the whole split: moving a refusal to 3 must not have moved the
        # finding code.
        module = self.module()
        self.assertEqual(module.EXIT_FINDING, 1)
        with mock.patch.object(module.shutil, "which", return_value="/stub/betterleaks"):
            with mock.patch.object(module, "run_scanner_batch", return_value=1):
                code = module.scan_paths(Path("/repo"), ["leaky.txt"], Path("/repo/config.toml"))
        self.assertEqual(code, module.EXIT_FINDING)

        # ... and a scanner's own non-finding code is still passed through unchanged.
        with mock.patch.object(module.shutil, "which", return_value="/stub/betterleaks"):
            with mock.patch.object(module, "run_scanner_batch", return_value=7):
                code = module.scan_paths(Path("/repo"), ["leaky.txt"], Path("/repo/config.toml"))
        self.assertEqual(code, 7)

    def test_the_finding_code_is_the_scanners_own_and_every_other_code_is_ambiguous(self) -> None:
        """agentic-sdlc-8c3f: what actually holds a found leak on Decision 9's 1.

        The docstring used to say `mise run check` depends on the exact value. It does not — the
        task is reached through `depends` and lefthook runs `mise run secrets`, so both consumers
        read nonzero and nothing in the tree compares this status to a literal. The real constraint
        is the pass-through: every scanner code outside {0, 1} reaches the caller unchanged, so a
        wrapper verdict placed anywhere in that space cannot be told apart from betterleaks
        returning the same number for its own reasons. 1 is the only value where the two mean the
        same event. This asserts that structurally rather than restating the number.
        """
        module = self.module()
        scanner_finding_code = 1

        # The wrapper's own verdict and the scanner's report of a finding are one code.
        self.assertEqual(module.EXIT_FINDING, scanner_finding_code)

        # ...and every other nonzero is already spoken for by the scanner, which is what makes any
        # of them an ambiguous home for the verdict rather than a free slot.
        for scanner_code in (2, 3, 4, 5, 6, 7, 8):
            with self.subTest(scanner_code=scanner_code):
                with mock.patch.object(module.shutil, "which", return_value="/stub/betterleaks"):
                    with mock.patch.object(module, "run_scanner_batch", return_value=scanner_code):
                        observed = module.scan_paths(
                            Path("/repo"), ["leaky.txt"], Path("/repo/config.toml")
                        )
                self.assertEqual(observed, scanner_code)
                self.assertNotEqual(
                    module.EXIT_FINDING,
                    scanner_code,
                    "the finding verdict must not occupy a code the scanner can also return",
                )


if __name__ == "__main__":
    unittest.main()
