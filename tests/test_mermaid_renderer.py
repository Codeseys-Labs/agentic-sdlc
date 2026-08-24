from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts import render_mermaid_linux as renderer


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "mermaid-renderer"
POLICY_PATH = ROOT / "policy" / "mermaid-renderer-linux-v1.json"

# `_sandbox_argv` refuses to build an argv when the pinned bwrap is absent, which is correct
# for the renderer and wrong for these two tests: they assert the SHAPE of the argv and never
# execute it. On a host without bwrap (a fresh container, notably) they errored instead of
# skipping, which made the gate fail for a capability the gate does not require — rendering is
# advisory. The capability is a real precondition for rendering, so it is named in the skip
# rather than faked.
SANDBOX_BINARY = Path(json.loads(POLICY_PATH.read_text(encoding="utf-8"))["sandbox"]["bwrap"])
SANDBOX_AVAILABLE = SANDBOX_BINARY.is_file() and not SANDBOX_BINARY.is_symlink()
SANDBOX_SKIP_REASON = f"the pinned sandbox binary {SANDBOX_BINARY} is unavailable on this host"

# Past the arity/help gate the wrapper returns EXIT_UNSUPPORTED off Linux x64 before it reads any
# path, so a test that asserts a later code must name that host requirement instead of failing.
LINUX_X64 = sys.platform == "linux" and os.uname().machine in {"x86_64", "amd64"}
LINUX_X64_SKIP_REASON = "the renderer is certified for Linux x64 only; other hosts return 3 first"

# Narrower than LINUX_X64 on purpose: the fixtures below assert POSIX facts directly --
# 0o700/0o600 mode bits, `os.getuid` ownership, npm's symlink `.bin` shims -- which Windows
# cannot represent (npm writes .cmd shims there and `os.getuid` does not exist), while any
# POSIX host (the macOS notes in this file are load-bearing) still exercises them for real.
POSIX_SEMANTICS = os.name != "nt"
POSIX_SEMANTICS_SKIP_REASON = (
    "owner-private mode bits, os.getuid ownership, and npm symlink shims are POSIX semantics"
    " with no Windows equivalent"
)



class MermaidRendererTests(unittest.TestCase):
    def test_help_exits_zero_and_prints_the_two_positional_usage(self) -> None:
        with mock.patch.object(
            renderer, "load_policy", side_effect=AssertionError("--help must not render")
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = renderer.main(["--help"])
        self.assertEqual(code, renderer.EXIT_OK)
        self.assertIn("render_mermaid_linux.py <definition> <final-svg>", buffer.getvalue())

    def test_short_help_flag_also_exits_zero_without_rendering(self) -> None:
        with mock.patch.object(
            renderer, "load_policy", side_effect=AssertionError("-h must not render")
        ):
            code = renderer.main(["-h"])
        self.assertEqual(code, renderer.EXIT_OK)

    def test_argv_none_dispatch_reads_the_real_sys_argv(self) -> None:
        # `main()` is what `if __name__ == "__main__"` calls, with no argument at all, so the
        # `argv is None` path must read the real `sys.argv`. Every other test here passes an
        # explicit list and would still pass if that path were broken.
        with mock.patch.object(sys, "argv", ["render_mermaid_linux.py", "--help"]):
            with mock.patch.object(
                renderer, "load_policy", side_effect=AssertionError("--help must not render")
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    code = renderer.main()
        self.assertEqual(code, renderer.EXIT_OK)
        self.assertIn("render_mermaid_linux.py <definition> <final-svg>", buffer.getvalue())

        # Positive control on the same `argv is None` path: a bare real `sys.argv` is the wrong
        # arity, so it must be refused with a named reason rather than treated as help.
        with mock.patch.object(sys, "argv", ["render_mermaid_linux.py"]):
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = renderer.main()
        self.assertEqual(code, renderer.EXIT_USAGE)
        self.assertIn("received 0", buffer.getvalue())

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_help_with_a_second_argument_is_a_render_request_not_the_help_path(self) -> None:
        # Positive control bounding the new help branch: `--help` is the 0-class query only as
        # the WHOLE argv. With a second argument the call has the renderer's exact arity, so it
        # is a render request whose definition path happens to be spelled `--help`, and it must
        # be refused as an unusable input instead of being answered with usage on STDOUT. The
        # refusal is now the input class (2, agentic-sdlc-4e2e) and its text goes to stderr, so
        # the distinction this test protects — a question answered versus a request refused — is
        # still the empty stdout, not the code.
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "destination.svg"
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = renderer.main(["--help", str(destination)])
        self.assertEqual(code, renderer.EXIT_USAGE)
        self.assertIn("input path must be absolute and traversal-free", err.getvalue())
        self.assertEqual(out.getvalue(), "", "usage must not be printed for a render request")
        self.assertFalse(destination.exists())

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_a_supplied_but_missing_definition_exits_two_not_one(self) -> None:
        """agentic-sdlc-4e2e: the survey's input axis forbids landing this operand on 1.

        `render <missing> <out>` completed no work and refused because the operand the caller
        supplied is not a usable definition file. Exiting 1 made that indistinguishable from the
        sandbox or the browser failing mid-render — the same defect the sibling manifest refusal
        closed in agentic-sdlc-f83f. The negative control below is the one that matters: a
        RendererError raised BELOW the input admission must still be 1, so this is a reclassified
        input class rather than a blanket remap of the wrapper's failures onto 2.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "destination.svg"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = renderer.main([str(root / "no-such-definition.mmd"), str(destination)])
            self.assertEqual(code, renderer.EXIT_USAGE)
            stderr = err.getvalue()
            self.assertIn("render_mermaid_linux.py <definition> <final-svg>", stderr)
            self.assertIn("cannot inspect input", stderr)
            self.assertIn("no-such-definition.mmd", stderr)
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(destination.exists())

            # Negative control: a real definition, refused after admission, is still EXIT_ERROR.
            source = root / "definition.mmd"
            source.write_text("flowchart TD\nA-->B\n", encoding="utf-8")
            with mock.patch.object(
                renderer,
                "_private_workspace",
                side_effect=renderer.RendererError("workspace refused (test double)"),
            ):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(
                        renderer.main([str(source), str(destination)]), renderer.EXIT_ERROR
                    )
            self.assertFalse(destination.exists())

    def test_wrong_arity_exits_two_and_names_the_reason_on_stderr(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = renderer.main([])
        self.assertEqual(code, renderer.EXIT_USAGE)
        stderr = buffer.getvalue()
        self.assertIn("render_mermaid_linux.py <definition> <final-svg>", stderr)
        self.assertIn("error:", stderr)

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_two_argument_call_is_unaffected_by_the_new_help_path(self) -> None:
        # Positive control for SP-9: the ordinary two-positional path must still reach past the
        # arity/help gate into the real renderer logic, proving --help was added without
        # widening what the wrapper will render.
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "definition.mmd"
            destination = Path(temp) / "destination.svg"
            source.write_text("flowchart TD\nA-->B\n", encoding="utf-8")
            with mock.patch.object(
                renderer,
                "_runtime_receipt",
                side_effect=renderer.RendererError("missing receipt (test double)"),
            ):
                code = renderer.main([str(source), str(destination)])
        self.assertEqual(code, renderer.EXIT_ERROR)
        self.assertFalse(destination.exists())

    def test_cli_rejects_extra_arguments_before_touching_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "preserved.svg"
            before = b"previous bytes"
            destination.write_bytes(before)
            code = renderer.main([str(FIXTURES / "trusted-flowchart.mmd"), str(destination), "--caller-config"])
            self.assertEqual(code, renderer.EXIT_USAGE)
            self.assertEqual(destination.read_bytes(), before)

    def test_cli_returns_unsupported_before_touching_paths_off_linux(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "definition.mmd"
            destination = root / "destination.svg"
            source.write_text("flowchart TD\nA-->B\n", encoding="utf-8")
            with mock.patch.object(renderer.sys, "platform", "darwin"):
                code = renderer.main([str(source), str(destination)])
            self.assertEqual(code, renderer.EXIT_UNSUPPORTED)
            self.assertFalse(destination.exists())

    @unittest.skipUnless(LINUX_X64, LINUX_X64_SKIP_REASON)
    def test_source_config_directive_is_rejected_before_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "hostile.mmd"
            destination = Path(temp) / "result.svg"
            source.write_text("%%{init: {'securityLevel': 'loose'}}%%\nflowchart TD\nA-->B\n", encoding="utf-8")
            with mock.patch.object(renderer, "_runtime_receipt", side_effect=AssertionError("render reached")):
                self.assertEqual(renderer.main([str(source), str(destination)]), renderer.EXIT_ERROR)
            self.assertFalse(destination.exists())

    def test_final_validation_accepts_allowlisted_fragment_svg(self) -> None:
        policy = renderer.load_policy(POLICY_PATH)
        valid = (FIXTURES / "allowed.svg").read_bytes()
        self.assertEqual(renderer.validate_final_svg(valid, policy), renderer.validate_final_svg(valid, policy))

    def test_final_validation_rejects_each_adversarial_fixture(self) -> None:
        policy = renderer.load_policy(POLICY_PATH)
        corpus = json.loads((FIXTURES / "corpus.json").read_text(encoding="utf-8"))
        for entry in corpus["fixtures"]:
            if entry["status"] != "rejected":
                continue
            with self.subTest(entry=entry["path"]), self.assertRaises(renderer.RendererError):
                renderer.validate_final_svg((FIXTURES / entry["path"]).read_bytes(), policy)

    def test_final_validation_rejects_unknown_css_property(self) -> None:
        policy = renderer.load_policy(POLICY_PATH)
        value = b'<svg xmlns="http://www.w3.org/2000/svg"><style>svg{unknown-property:1}</style></svg>'
        with self.assertRaises(renderer.RendererError):
            renderer.validate_final_svg(value, policy)

    def test_atomic_publication_preserves_prior_destination_on_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "published.svg"
            before = b"known-good"
            destination.write_bytes(before)
            with self.assertRaises(renderer.RendererError):
                renderer.publish_final(destination, (FIXTURES / "forbidden-active.svg").read_bytes(), renderer.load_policy(POLICY_PATH))
            self.assertEqual(destination.read_bytes(), before)

    @unittest.skipUnless(POSIX_SEMANTICS, POSIX_SEMANTICS_SKIP_REASON)
    def test_generated_configs_have_only_policy_keys(self) -> None:
        policy = renderer.load_policy(POLICY_PATH)
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            browser = workspace / "chrome-headless-shell"
            browser.write_bytes(b"browser")
            mermaid, puppeteer = renderer.write_owner_configs(workspace, browser, policy)
            self.assertEqual(set(json.loads(mermaid.read_text(encoding="utf-8"))), set(policy["mermaid_config"]))
            self.assertEqual(set(json.loads(puppeteer.read_text(encoding="utf-8"))), set(policy["puppeteer_config"]))
            self.assertEqual(oct(mermaid.stat().st_mode & 0o777), "0o600")
            self.assertEqual(oct(puppeteer.stat().st_mode & 0o777), "0o600")

    @unittest.skipUnless(POSIX_SEMANTICS, POSIX_SEMANTICS_SKIP_REASON)
    def test_node_bin_resolver_allows_npm_shim_only_when_target_stays_in_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            # RESOLVED ONCE, HERE, because `resolve_node_bin_shim` returns `shim.resolve(strict=True)`.
            # On macOS `$TMPDIR` lives under `/var/folders/...` and `/var` is a symlink to
            # `/private/var`, so `mkdtemp()` hands back the unresolved spelling while the resolver
            # hands back the resolved one -- two spellings of one file, and the assertion fails on a
            # path the resolver never got wrong. The shim symlink this test actually exercises is
            # created BELOW this root afterwards, so resolving the root cannot resolve it away.
            root = Path(temp).resolve()
            package = root / "node_modules" / "package" / "cli.mjs"
            package.parent.mkdir(parents=True)
            package.write_text("", encoding="utf-8")
            shim = root / "node_modules" / ".bin" / "tool"
            shim.parent.mkdir()
            shim.symlink_to("../package/cli.mjs")
            self.assertEqual(renderer.resolve_node_bin_shim(shim, root / "node_modules"), package)
            shim.unlink()
            shim.symlink_to("/etc/passwd")
            with self.assertRaises(renderer.RendererError):
                renderer.resolve_node_bin_shim(shim, root / "node_modules")

    def test_node_modules_digest_detects_npm_shim_retargeting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            modules = Path(temp) / "node_modules"
            package = modules / "package"
            package.mkdir(parents=True)
            (package / "first.mjs").write_text("same bytes", encoding="utf-8")
            (package / "second.mjs").write_text("same bytes", encoding="utf-8")
            shim = modules / ".bin" / "tool"
            shim.parent.mkdir()
            shim.symlink_to("../package/first.mjs")
            first = renderer._node_modules_digest(modules)
            shim.unlink()
            shim.symlink_to("../package/second.mjs")
            self.assertNotEqual(first, renderer._node_modules_digest(modules))

    def test_process_tree_rss_sums_descendant_resident_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            proc = Path(temp) / "proc"
            for pid, children, rss in (("100", "101 102", 3), ("101", "", 5), ("102", "", 7)):
                task = proc / pid / "task" / pid
                task.mkdir(parents=True)
                (task / "children").write_text(children, encoding="utf-8")
                (proc / pid / "status").write_text(f"Name:\ttest\nVmRSS:\t{rss} kB\n", encoding="utf-8")
            self.assertEqual(renderer._process_tree_rss(100, proc), 15 * 1024)

    def test_aggregate_deadline_bounds_each_renderer_child(self) -> None:
        with mock.patch.object(renderer.time, "monotonic", return_value=11.0):
            self.assertEqual(renderer._remaining_timeout(13.0, 5, "render"), 2.0)
        with mock.patch.object(renderer.time, "monotonic", return_value=13.0), self.assertRaises(renderer.RendererError):
            renderer._remaining_timeout(13.0, 5, "render")

    @unittest.skipUnless(POSIX_SEMANTICS, POSIX_SEMANTICS_SKIP_REASON)
    def test_renderer_passes_absolute_child_deadlines(self) -> None:
        # renderer.ROOT is redirected at a throwaway repo so the fake browser cache never
        # lands in the working tree: a unit test must not leave a provisioned-looking runtime
        # behind for a later real provision to inherit.
        policy = renderer.load_policy(POLICY_PATH)
        existed = (ROOT / ".mermaid-runtime").exists()
        with tempfile.TemporaryDirectory() as temp:
            # Same macOS root cause, different symptom: `_render` walks every ancestor of the patched
            # cache through `_safe_parent_chain`, and the `/var` -> `/private/var` symlink above
            # `$TMPDIR` makes it refuse this fixture outright instead of mismatching a spelling. What
            # is asserted here is deadline arithmetic, not platform support, and the fixture creates
            # no symlink of its own, so resolving the root is safe -- the refusal still guards every
            # path a real render walks.
            base = Path(temp).resolve()
            root = base / "workspace"
            root.mkdir()
            repo = base / "repo"
            (repo / "scripts").mkdir(parents=True)
            (repo / "scripts" / "sanitize_mermaid_svg.mjs").write_text("", encoding="utf-8")
            executable = repo / policy["paths"]["cache_root"] / policy["browser"]["executable_relative_path"]
            executable.parent.mkdir(parents=True)
            executable.touch()
            (root / "raw.svg").write_bytes(b"<svg xmlns=\"http://www.w3.org/2000/svg\"/>")
            (root / "final.svg").write_bytes(b"<svg xmlns=\"http://www.w3.org/2000/svg\"/>")
            # A fixture file, not the host's `/bin/true`: `_render` only asks `is_file()` of the
            # verified tools (`_run_child` is mocked, so nothing executes), and macOS has no
            # `/bin/true` -- reading the host's filesystem layout is what failed this test there.
            tool_stand_in = base / "verified-tool"
            tool_stand_in.touch()
            with mock.patch.object(renderer, "ROOT", repo), mock.patch.object(renderer, "_runtime_receipt", return_value={"node_executable": str(tool_stand_in)}), mock.patch.object(renderer, "_cache_digest", return_value=policy["browser"]["cache_tree_sha256"]), mock.patch.object(renderer, "_sha256", return_value=policy["browser"]["executable_sha256"]), mock.patch.object(renderer, "resolve_node_bin_shim", return_value=tool_stand_in), mock.patch.object(renderer, "write_owner_configs", return_value=(root / "mermaid.json", root / "puppeteer.json")), mock.patch.object(renderer, "_run_child") as child, mock.patch.object(renderer.time, "monotonic", side_effect=[10.0, 10.0, 12.0, 12.0]):
                renderer._render(b"flowchart TD\\nA-->B\\n", root, policy, 20.0)
            # The unit test must not fabricate a runtime directory; on an already-provisioned
            # host a real one may legitimately exist, so only the creation is asserted.
            self.assertEqual(existed, (ROOT / ".mermaid-runtime").exists())
        self.assertEqual(child.call_args_list[0].args[2], 20.0)
        self.assertEqual(child.call_args_list[1].args[2], 20.0)

    @unittest.skipUnless(SANDBOX_AVAILABLE, SANDBOX_SKIP_REASON)
    def test_sandbox_relocates_runtime_inputs_under_a_private_fixed_prefix(self) -> None:
        policy = renderer.load_policy(POLICY_PATH)
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            bindings = [(Path("/bin/sh"), renderer.SANDBOX_NODE), (Path("/usr/bin/env"), renderer.SANDBOX_POLICY)]
            argv = renderer._sandbox_argv(workspace, [renderer.SANDBOX_NODE, renderer.SANDBOX_POLICY], policy, readonly_paths=bindings)
        self.assertIn("--dir", argv)
        self.assertIn(renderer.SANDBOX_ROOT, argv)
        self.assertIn(renderer.SANDBOX_NODE, argv)
        self.assertIn(renderer.SANDBOX_POLICY, argv)
        self.assertNotIn("/bin/sh", argv[argv.index("--") + 1:])

    @unittest.skipUnless(SANDBOX_AVAILABLE, SANDBOX_SKIP_REASON)
    def test_sandbox_binds_only_the_verified_runtime_inputs(self) -> None:
        policy = renderer.load_policy(POLICY_PATH)
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            bindings = [(Path("/bin/sh"), renderer.SANDBOX_NODE), (Path("/usr/bin/env"), renderer.SANDBOX_POLICY)]
            argv = renderer._sandbox_argv(workspace, [renderer.SANDBOX_NODE, renderer.SANDBOX_POLICY], policy, readonly_paths=bindings)
        self.assertIn("--unshare-net", argv)
        self.assertNotIn("--ro-bind / /", " ".join(argv))
        for runtime_path in (renderer.SANDBOX_NODE, renderer.SANDBOX_POLICY):
            self.assertIn(runtime_path, argv)

    def test_sanitizer_rejects_forbidden_raw_svg_before_writing_output(self) -> None:
        # The sanitizer's pre-DOM rejection is pure text, so any Node runs it; the pinned Node
        # matters only for the real render, which lives in the tests_linux suite.
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node is required for the sanitizer pre-DOM rejection test")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw.svg"
            output = root / "final.svg"
            raw.write_bytes((FIXTURES / "forbidden-active.svg").read_bytes())
            process = subprocess.run([node, str(ROOT / "scripts" / "sanitize_mermaid_svg.mjs"), str(raw), str(output), str(POLICY_PATH)], text=True, capture_output=True, check=False)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
