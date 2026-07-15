from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
LAUNCHER = ROOT / "skills" / "agentic-sdlc-orchestrator" / "tools" / "seeds-launcher.mjs"
NODE = shutil.which("node")


@unittest.skipIf(NODE is None or os.name == "nt", "Node and POSIX fixture executables are required for isolated launcher execution fixtures")
class SeedsLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.distribution = self.root / "reviewed distribution"
        self.distribution.mkdir()
        (self.distribution / "mise.toml").write_text("[tools]\nnode = '22.22.3'\n", encoding="utf-8")
        (self.distribution / "mise.lock").write_text("locked fixture\n", encoding="utf-8")
        self._run(["git", "init", "-q"], cwd=self.distribution)
        self._run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.distribution)
        self._run(["git", "config", "user.name", "Fixture"], cwd=self.distribution)
        self._run(["git", "add", "."], cwd=self.distribution)
        self._run(["git", "commit", "-qm", "fixture"], cwd=self.distribution)

        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "mise.jsonl"
        self.bun_log = self.root / "bun.log"
        self.bun_behavior = self.root / "bun-behavior"
        self.bun_behavior.write_text("0", encoding="utf-8")
        self.node_root = self.root / "installs" / "node" / "22.22.3"
        self.bun_root = self.root / "installs" / "bun" / "1.3.10"
        self.seeds_root = self.root / "installs" / "npm-os-eco-seeds-cli" / "0.5.14"
        self._make_tool_layout()
        git = shutil.which("git.exe" if os.name == "nt" else "git")
        if not git:
            self.skipTest("Git is required for launcher fixtures")
        git_name = "git.exe" if os.name == "nt" else "git"
        if os.name == "nt":
            os.symlink(git, self.bin / git_name)
        else:
            self._write_executable(self.bin / git_name, f"#!/bin/sh\nexec {self._quote(git)} \"$@\"\n")
        self._write_mise()
        self.target = self.root / "hostile target"
        self.target.mkdir()
        (self.target / "bunfig.toml").write_text("preload = ['./hostile.ts']\n", encoding="utf-8")
        (self.target / ".env").write_text("BUN_OPTIONS=--hot\n", encoding="utf-8")
        (self.target / "package.json").write_text('{"bun":{"preload":["hostile"]}}\n', encoding="utf-8")
        self.state = self.root / "state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True, check=True)

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("'", "'\\''") + "'"

    def _write_executable(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _make_tool_layout(self) -> None:
        host_node = self._quote(str(Path(NODE).resolve()))
        self._write_executable(
            self.node_root / "bin" / "node",
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = --version ]; then printf 'v22.22.3\\n'; exit 0; fi\n"
            f"exec {host_node} \"$@\"\n",
        )
        environment_command = self._quote(str(shutil.which("env")))
        sort_command = self._quote(str(shutil.which("sort")))
        cat_command = self._quote(str(shutil.which("cat")))
        self._write_executable(
            self.bun_root / "bin" / "bun",
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = --version ]; then printf '1.3.10\\n'; exit 0; fi\n"
            f"printf '%s\\n' \"$*\" >> {self._quote(str(self.bun_log))}\n"
            f"{environment_command} | {sort_command} >> {self._quote(str(self.bun_log))}\n"
            f"if [ \"$({cat_command} {self._quote(str(self.bun_behavior))})\" = TERM ]; then kill -TERM $$; fi\n"
            f"exit \"$({cat_command} {self._quote(str(self.bun_behavior))})\"\n",
        )
        package = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli"
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            '{"name":"@os-eco/seeds-cli","version":"0.5.14","bin":{"sd":"./src/index.ts"}}\n',
            encoding="utf-8",
        )
        (package / "src").mkdir()
        (package / "src" / "index.ts").write_text("console.log('fixture')\n", encoding="utf-8")
        (self.seeds_root / "bin").mkdir(parents=True)
        os.symlink("../lib/node_modules/@os-eco/seeds-cli/src/index.ts", self.seeds_root / "bin" / "sd")

    def _write_mise(self) -> None:
        self._write_executable(
            self.bin / "mise",
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> {self._quote(str(self.calls))}\n"
            "if [ \"${1:-}\" = --no-config ] && [ \"${2:-}\" = where ]; then\n"
            "  case \"${3:-}\" in\n"
            f"    node@22.22.3) printf '%s\\n' {self._quote(str(self.node_root))} ;;\n"
            f"    bun@1.3.10) printf '%s\\n' {self._quote(str(self.bun_root))} ;;\n"
            f"    npm:@os-eco/seeds-cli@0.5.14) printf '%s\\n' {self._quote(str(self.seeds_root))} ;;\n"
            "    *) exit 2 ;;\n"
            "  esac\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"${1:-}\" = --locked ] && [ \"${2:-}\" = install ]; then exit 0; fi\n"
            "exit 2\n",
        )

    def environment(self) -> dict[str, str]:
        return os.environ | {
            "PATH": str(self.bin) + os.pathsep + os.defpath,
            "XDG_STATE_HOME": str(self.state),
            "BUN_OPTIONS": "--inspect=127.0.0.1:9229",
            "BUN_INSPECT_PRELOAD": "hostile",
            "NODE_OPTIONS": "--trace-warnings",
            "NPM_CONFIG_REGISTRY": "https://hostile.invalid/",
            "MISE_DATA_DIR": str(self.root / "hostile-mise-data"),
            "SEEDS_DEBUG": "1",
        }

    def launcher(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [NODE, str(LAUNCHER), *args],
            text=True,
            capture_output=True,
            env=env or self.environment(),
            check=False,
        )

    def bootstrap(self) -> subprocess.CompletedProcess[str]:
        return self.launcher("bootstrap", "--distribution", str(self.distribution))

    def test_bootstrap_is_locked_validates_exact_tuple_and_publishes_active_prior_receipts(self) -> None:
        first = self.bootstrap()
        self.assertEqual(first.returncode, 0, first.stderr)
        calls = self.calls.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls[0], "--locked install")
        self.assertEqual(calls[1:], [
            "--no-config where node@22.22.3",
            "--no-config where bun@1.3.10",
            "--no-config where npm:@os-eco/seeds-cli@0.5.14",
        ])
        active = self.state / "agentic-sdlc-orchestrator" / "seeds-runtime" / "v1" / "active.json"
        receipt = json.loads(active.read_text(encoding="utf-8"))
        self.assertEqual(receipt["tuple"]["node"]["version"], "22.22.3")
        self.assertEqual(receipt["tuple"]["bun"]["version"], "1.3.10")
        self.assertEqual(receipt["tuple"]["seeds"]["package"], "@os-eco/seeds-cli")
        self.assertEqual(receipt["tuple"]["seeds"]["bin"], "sd")
        self.assertIn("distribution", receipt["hashes"])
        self.assertTrue((active.parent / "trusted-bunfig.toml").is_file())
        self.assertEqual((active.parent / "trusted-bunfig.toml").read_bytes(), b"")
        second = self.bootstrap()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((active.parent / "previous.json").is_file())

    def test_bootstrap_rejects_package_execution_controls_before_receipt_publication(self) -> None:
        package = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli" / "package.json"
        package.write_text(
            '{"name":"@os-eco/seeds-cli","version":"0.5.14","bin":{"sd":"./src/index.ts"},"preload":["hostile"]}\n',
            encoding="utf-8",
        )
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("execution control", result.stderr)
        self.assertFalse((self.state / "agentic-sdlc-orchestrator" / "seeds-runtime" / "v1" / "active.json").exists())

    def test_inspect_uses_receipt_never_mise_and_filters_environment_before_exact_bun(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        before = self.calls.read_text(encoding="utf-8")
        result = self.launcher("inspect", "--target", str(self.target), "ready", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), before)
        contents = self.bun_log.read_text(encoding="utf-8")
        self.assertIn("--config=", contents)
        self.assertIn("--no-env-file --no-install", contents)
        self.assertIn("ready --format json", contents)
        self.assertIn(f"PWD={self.target}", contents)
        for hostile in ("BUN_OPTIONS=", "BUN_INSPECT_PRELOAD=", "NODE_OPTIONS=", "NPM_CONFIG_REGISTRY=", "MISE_DATA_DIR=", "SEEDS_DEBUG="):
            self.assertNotIn(hostile, contents)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", contents)

    def test_inspect_rejects_missing_partial_drifted_receipt_and_invalid_grammar_before_bun(self) -> None:
        missing = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse(self.bun_log.exists())
        self.assertEqual(self.bootstrap().returncode, 0)
        active = self.state / "agentic-sdlc-orchestrator" / "seeds-runtime" / "v1" / "active.json"
        active.write_text('{"schema":1}\n', encoding="utf-8")
        partial = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertNotEqual(partial.returncode, 0)
        self.assertFalse(self.bun_log.exists())
        active.unlink()
        self.assertEqual(self.bootstrap().returncode, 0)
        (self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli" / "src" / "index.ts").write_text("changed\n", encoding="utf-8")
        drift = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertNotEqual(drift.returncode, 0)
        self.assertFalse(self.bun_log.exists())
        self.assertEqual(self.bootstrap().returncode, 0)
        grammar = self.launcher("inspect", "--target", str(self.target), "create", "no")
        self.assertNotEqual(grammar.returncode, 0)
        self.assertFalse(self.bun_log.exists())

    def test_inspect_preserves_exact_child_exit_code_and_signal(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        self.bun_behavior.write_text("23", encoding="utf-8")
        failed = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertEqual(failed.returncode, 23, failed.stderr)
        self.bun_behavior.write_text("TERM", encoding="utf-8")
        signaled = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertEqual(signaled.returncode, -15, signaled.stderr)

    def test_installed_launcher_and_posix_windows_runbooks_keep_exact_exit_and_cleanup_contracts(self) -> None:
        self.assertTrue(LAUNCHER.is_file(), "the installed flagship skill must contain the launcher")
        self.assertIn("bin', 'bun.exe", LAUNCHER.read_text(encoding="utf-8"))
        posix = (ROOT / "scripts" / "check-agentic-sdlc-prereqs.sh").read_text(encoding="utf-8")
        windows = (ROOT / "scripts" / "run-windows-mise.ps1").read_text(encoding="utf-8")
        self.assertIn("mise --no-config where", posix)
        self.assertIn("cleanup", posix)
        self.assertIn("child_status=$?", posix)
        self.assertIn("'--no-config' 'where' 'node@22.22.3'", windows)
        self.assertIn("finally", windows)
        self.assertIn("$childStatus = $LASTEXITCODE", windows)


if __name__ == "__main__":
    unittest.main()
