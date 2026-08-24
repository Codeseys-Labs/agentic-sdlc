from __future__ import annotations

import ast
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import provision_mermaid_linux as provisioner


# Mirrors tests/test_mermaid_renderer.py: off Linux x64 the provisioner refuses first
# ("mermaid-provision: Linux x64 only", exit 3) before any later refusal or post-boundary
# failure can be reached, so a test asserting one of those later exits or stderr messages
# must name that host requirement instead of failing.
LINUX_X64 = sys.platform == "linux" and os.uname().machine in {"x86_64", "amd64"}
LINUX_X64_SKIP_REASON = (
    "the provisioner is certified for Linux x64 only; other hosts refuse at 3 first"
)


class ProvisionMermaidLinuxArgvTests(unittest.TestCase):
    """SP-3: --help and an unknown flag must not reach `provision()` (no download); a bare
    invocation -- the exact shape of the `mermaid:provision` mise task -- must still reach it.
    """

    def test_help_exits_zero_and_prints_the_usage_line_without_provisioning(self) -> None:
        with mock.patch.object(
            provisioner, "provision", side_effect=AssertionError("--help must not provision")
        ) as sentinel:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    provisioner.main(["--help"])

        self.assertEqual(ctx.exception.code, provisioner.EXIT_OK)
        # The usage line must actually reach stdout: a `print_help` that emits nothing would
        # otherwise pass on the exit code alone.
        self.assertIn("usage: provision_mermaid_linux.py", buffer.getvalue())
        sentinel.assert_not_called()

    def test_short_help_flag_also_exits_zero_without_provisioning(self) -> None:
        with mock.patch.object(
            provisioner, "provision", side_effect=AssertionError("-h must not provision")
        ) as sentinel:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    provisioner.main(["-h"])

        self.assertEqual(ctx.exception.code, provisioner.EXIT_OK)
        self.assertIn("usage: provision_mermaid_linux.py", buffer.getvalue())
        sentinel.assert_not_called()

    def test_unknown_flag_exits_two_before_provisioning(self) -> None:
        with mock.patch.object(
            provisioner, "provision", side_effect=AssertionError("--zzz must not provision")
        ) as sentinel:
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    provisioner.main(["--zzz-not-a-flag"])

        self.assertEqual(ctx.exception.code, provisioner.EXIT_USAGE)
        self.assertIn("unrecognized arguments", buffer.getvalue())
        sentinel.assert_not_called()

    def test_stray_positional_argument_exits_two_before_provisioning(self) -> None:
        with mock.patch.object(
            provisioner,
            "provision",
            side_effect=AssertionError("a stray positional must not provision"),
        ) as sentinel:
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    provisioner.main(["stray"])

        self.assertEqual(ctx.exception.code, provisioner.EXIT_USAGE)
        self.assertIn("unrecognized arguments", buffer.getvalue())
        sentinel.assert_not_called()

    def test_no_arguments_still_reaches_the_real_provision_entry_point(self) -> None:
        # Positive control for the refusals above: a bare invocation -- the mise
        # mermaid:provision task's exact shape -- must still dispatch into `provision()`.
        # `provision` is monkeypatched so no browser is actually downloaded; this proves the
        # dispatch reaches the operation entry rather than proving the operations above are
        # vacuous no-ops that nothing ever calls.
        with mock.patch.object(provisioner, "provision", return_value=None) as sentinel:
            code = provisioner.main([])

        sentinel.assert_called_once()
        self.assertEqual(code, provisioner.EXIT_OK)

    def test_argv_none_dispatch_reads_the_real_sys_argv(self) -> None:
        # `main()` is what `if __name__ == "__main__"` calls, with no argument at all, so the
        # `argv is None` path must reach argparse through the real `sys.argv`. Every other test
        # here passes an explicit list and would still pass if that path were broken.
        with mock.patch.object(sys, "argv", ["provision_mermaid_linux.py", "--zzz-not-a-flag"]):
            with mock.patch.object(
                provisioner, "provision", side_effect=AssertionError("sys.argv must be parsed")
            ) as refused:
                buffer = io.StringIO()
                with contextlib.redirect_stderr(buffer):
                    with self.assertRaises(SystemExit) as ctx:
                        provisioner.main()

        self.assertEqual(ctx.exception.code, provisioner.EXIT_USAGE)
        self.assertIn("unrecognized arguments", buffer.getvalue())
        refused.assert_not_called()

        # Positive control on the same `argv is None` path: a bare real `sys.argv` provisions.
        with mock.patch.object(sys, "argv", ["provision_mermaid_linux.py"]):
            with mock.patch.object(provisioner, "provision", return_value=None) as reached:
                code = provisioner.main()

        reached.assert_called_once()
        self.assertEqual(code, provisioner.EXIT_OK)


class ProvisionExitSplitTests(unittest.TestCase):
    """SP-3's third clause: the 3-versus-4 split. A refusal above the effect boundary is
    EXIT_REFUSED and provably leaves the tree alone; a failure at or after `npm ci` / the
    browser install is EXIT_PARTIAL. No test here downloads anything: every post-boundary
    failure is injected at the `_run` / shim / hash seams.
    """

    def tree(self, temp: str) -> Path:
        """A stand-in repository root with a `node_modules` sentinel the provisioner deletes."""
        root = Path(temp)
        (root / "node_modules").mkdir()
        (root / "node_modules" / "marker.txt").write_text("pre-existing\n", encoding="utf-8")
        return root

    def assert_untouched(self, root: Path) -> None:
        self.assertFalse((root / ".mermaid-runtime").exists(), "no runtime directory may exist")
        self.assertTrue(
            (root / "node_modules" / "marker.txt").is_file(),
            "a pre-effect refusal must not delete node_modules",
        )

    def fake_toolchain(self, root: Path, *, executables: bool = True) -> tuple[Path, Path]:
        node_bin = root / "tools" / "node" / "bin"
        npm_bin = root / "tools" / "npm" / "bin"
        for directory, name in ((node_bin, "node"), (npm_bin, "npm")):
            directory.mkdir(parents=True)
            if executables:
                (directory / name).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        return node_bin, npm_bin

    def where(self, node_bin: Path, npm_bin: Path):
        def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            target = node_bin.parent if argv[-1].startswith("node@") else npm_bin.parent
            return subprocess.CompletedProcess(argv, 0, f"{target}\n", "")

        return run

    def provision_exit(
        self, root: Path, *, observed_platform: str = "linux", observed_machine: str = "x86_64"
    ) -> tuple[int, str]:
        """Drive `main` under an INJECTED platform observation, certified by default.

        What this class proves is the 3-versus-4 effect-boundary split, which sits BEHIND the
        provisioner's Linux-x64 gate; injecting the certified pair (strictly stronger than
        skipping -- the split stays proved on every host) keeps that gate from answering first on
        a host it would refuse. The gate itself keeps its own explicit darwin case below, which
        passes its refused platform through this same parameter. `create=True` because `os.uname`
        does not exist on Windows, where the gate's `sys.platform` clause short-circuits anyway.
        """
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            with mock.patch.object(provisioner, "ROOT", root):
                with mock.patch.object(provisioner.sys, "platform", observed_platform):
                    with mock.patch.object(
                        provisioner.os,
                        "uname",
                        create=True,
                        return_value=SimpleNamespace(machine=observed_machine),
                    ):
                        code = provisioner.main([])
        return code, buffer.getvalue()

    def test_non_linux_host_refuses_at_three_before_reading_the_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            with mock.patch.object(
                provisioner.renderer,
                "load_policy",
                side_effect=AssertionError("the platform refusal comes first"),
            ) as policy:
                code, stderr = self.provision_exit(root, observed_platform="darwin")

            self.assertEqual(code, provisioner.EXIT_REFUSED)
            self.assertIn("Linux x64 only", stderr)
            policy.assert_not_called()
            self.assert_untouched(root)

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_absent_mise_refuses_at_three_without_touching_the_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            with mock.patch.object(provisioner.shutil, "which", return_value=None):
                code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_REFUSED)
            self.assertIn("mise is required", stderr)
            self.assert_untouched(root)

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_unavailable_certified_tool_refuses_at_three_without_touching_the_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            failed = subprocess.CompletedProcess([], 1, "", "no such tool")
            with mock.patch.object(provisioner.shutil, "which", return_value="/stub/mise"):
                with mock.patch.object(provisioner.subprocess, "run", return_value=failed):
                    code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_REFUSED)
            self.assertIn("is unavailable", stderr)
            self.assert_untouched(root)

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_unsafe_certified_tool_path_refuses_at_three_without_touching_the_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            missing = subprocess.CompletedProcess([], 0, f"{root / 'absent-tool'}\n", "")
            with mock.patch.object(provisioner.shutil, "which", return_value="/stub/mise"):
                with mock.patch.object(provisioner.subprocess, "run", return_value=missing):
                    code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_REFUSED)
            self.assertIn("path is unsafe", stderr)
            self.assert_untouched(root)

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_missing_pinned_executables_refuse_at_three_and_keep_node_modules(self) -> None:
        # This is the test the reordering exists for: before the mkdir/rmtree block moved below
        # tool resolution, this refusal had already created `.mermaid-runtime` and deleted
        # `node_modules`, so its exit could not honestly claim nothing happened.
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            node_bin, npm_bin = self.fake_toolchain(root, executables=False)
            with mock.patch.object(provisioner.shutil, "which", return_value="/stub/mise"):
                with mock.patch.object(
                    provisioner.subprocess, "run", side_effect=self.where(node_bin, npm_bin)
                ):
                    code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_REFUSED)
            self.assertIn("pinned mise Node/npm executables are unavailable", stderr)
            self.assert_untouched(root)

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_npm_ci_failure_after_the_boundary_exits_four(self) -> None:
        # Positive control for the four refusals above: an honest post-`npm ci` failure must
        # NOT be reported as a clean pre-effect refusal, and the effect it claims really
        # happened (the runtime directory exists and `node_modules` is gone).
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            node_bin, npm_bin = self.fake_toolchain(root)
            with mock.patch.object(provisioner.shutil, "which", return_value="/stub/mise"):
                with mock.patch.object(
                    provisioner.subprocess, "run", side_effect=self.where(node_bin, npm_bin)
                ):
                    with mock.patch.object(
                        provisioner,
                        "_run",
                        side_effect=provisioner.ProvisionError("command failed: npm: EBADENGINE"),
                    ):
                        code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_PARTIAL)
            self.assertIn("command failed: npm", stderr)
            self.assertTrue((root / ".mermaid-runtime" / "cache").is_dir())
            self.assertFalse((root / "node_modules").exists())
            self.assertFalse((root / ".mermaid-runtime" / "runtime-receipt.json").exists())

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_browser_hash_mismatch_after_the_download_exits_four(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            node_bin, npm_bin = self.fake_toolchain(root)
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(provisioner.shutil, "which", return_value="/stub/mise"):
                with mock.patch.object(
                    provisioner.subprocess, "run", side_effect=self.where(node_bin, npm_bin)
                ):
                    with mock.patch.object(provisioner, "_run", return_value=completed):
                        with mock.patch.object(provisioner.renderer, "resolve_node_bin_shim"):
                            with mock.patch.object(provisioner, "_owner_only"):
                                with mock.patch.object(provisioner, "_sha256", return_value="00"):
                                    code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_PARTIAL)
            self.assertIn("browser hash or cache digest mismatch", stderr)
            self.assertFalse((root / ".mermaid-runtime" / "runtime-receipt.json").exists())

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_unsafe_npm_shim_after_the_download_exits_four_not_one(self) -> None:
        # `resolve_node_bin_shim` raises the renderer's error type, not the provisioner's. It is
        # still a post-download refusal, so it must land on 4 rather than escaping as a
        # traceback at 1.
        with tempfile.TemporaryDirectory() as temp:
            root = self.tree(temp)
            node_bin, npm_bin = self.fake_toolchain(root)
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(provisioner.shutil, "which", return_value="/stub/mise"):
                with mock.patch.object(
                    provisioner.subprocess, "run", side_effect=self.where(node_bin, npm_bin)
                ):
                    with mock.patch.object(provisioner, "_run", return_value=completed):
                        with mock.patch.object(
                            provisioner.renderer,
                            "resolve_node_bin_shim",
                            side_effect=provisioner.renderer.RendererError(
                                "npm executable shim escapes node_modules"
                            ),
                        ):
                            code, stderr = self.provision_exit(root)

            self.assertEqual(code, provisioner.EXIT_PARTIAL)
            self.assertIn("npm executable shim escapes node_modules", stderr)

    def test_the_exit_table_constants_hold_their_documented_values(self) -> None:
        # The module docstring's exit table is the derivation point; pin the numbers so a
        # renamed constant cannot silently move an operator-visible code.
        self.assertEqual(
            (
                provisioner.EXIT_OK,
                provisioner.EXIT_ERROR,
                provisioner.EXIT_USAGE,
                provisioner.EXIT_REFUSED,
                provisioner.EXIT_PARTIAL,
            ),
            (0, 1, 2, 3, 4),
        )
        self.assertTrue(issubclass(provisioner.ProvisionPartialError, provisioner.ProvisionError))

    def test_no_exit_site_can_choose_the_reserved_internal_failure_code(self) -> None:
        """agentic-sdlc-8c3f: `EXIT_ERROR = 1` is documented "reserved ... no refusal returns it".

        A docstring cannot enforce that. This is the source census that can: an AST walk over every
        `return`, `raise SystemExit(...)`, and `sys.exit(...)` in the module, asserting `EXIT_ERROR`
        appears in none of them, so the code is reachable only the way its reservation says — an
        uncaught exception, which the interpreter reports as 1 on its own. The planted control is
        what makes the census more than a spelling check: a `return EXIT_ERROR` grafted into the
        parsed source must be FOUND, otherwise a walk that misses every site would read as clean.
        """
        source = Path(provisioner.__file__).read_text(encoding="utf-8")

        def exit_sites_naming(text: str, name: str) -> list[int]:
            found: list[int] = []
            for node in ast.walk(ast.parse(text)):
                chosen: list[ast.expr] = []
                if isinstance(node, ast.Return) and node.value is not None:
                    chosen = [node.value]
                elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                    if getattr(node.exc.func, "id", None) == "SystemExit":
                        chosen = list(node.exc.args)
                elif isinstance(node, ast.Call):
                    target = node.func
                    if getattr(target, "attr", None) == "exit" or getattr(target, "id", None) == "exit":
                        chosen = list(node.args)
                for expression in chosen:
                    if any(
                        isinstance(inner, ast.Name) and inner.id == name
                        for inner in ast.walk(expression)
                    ):
                        found.append(node.lineno)
            return sorted(found)

        self.assertEqual(exit_sites_naming(source, "EXIT_ERROR"), [])

        # Positive control: the walk does reach the sites it claims to cover.
        planted = source.replace(
            "    try:\n        provision()",
            '    if argv == ["census-control"]:\n        return EXIT_ERROR\n    try:\n        provision()',
            1,
        )
        self.assertNotEqual(planted, source, "the anchor the control grafts onto has moved")
        self.assertNotEqual(exit_sites_naming(planted, "EXIT_ERROR"), [])

        # ...and the other four codes ARE chosen at explicit sites, so an empty result is a fact
        # about EXIT_ERROR rather than about the census.
        for name in ("EXIT_OK", "EXIT_REFUSED", "EXIT_PARTIAL"):
            with self.subTest(constant=name):
                self.assertNotEqual(exit_sites_naming(source, name), [])


if __name__ == "__main__":
    unittest.main()
