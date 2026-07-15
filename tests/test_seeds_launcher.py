from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).parents[1]
LAUNCHER = ROOT / "skills" / "agentic-sdlc-orchestrator" / "tools" / "seeds-launcher.mjs"
SEEDS_PACKAGE_FIXTURE = ROOT / "tests" / "fixtures" / "seeds-cli-0.5.14" / "package.json"
HOST_NODE = shutil.which("node")
HOSTILE_NODE = next(
    (
        str(candidate)
        for candidate in (
            Path("/home/linuxbrew/.linuxbrew/bin/node"),
            Path("/usr/local/bin/node"),
            Path("/usr/bin/node"),
        )
        if candidate.is_file()
        and subprocess.run([candidate, "--version"], text=True, capture_output=True, check=False).stdout.strip().removeprefix("v") != "22.22.3"
    ),
    None,
)
EXACT_NODE = Path(
    os.environ.get(
        "AGENTIC_SDLC_TEST_NODE",
        str(Path.home() / ".local" / "share" / "mise" / "installs" / "node" / "22.22.3" / ("node.exe" if os.name == "nt" else "bin/node")),
    )
)
NODE = str(EXACT_NODE) if EXACT_NODE.is_file() else HOST_NODE
RECEIPT_SCHEMA = 2


@unittest.skipIf(NODE is None or os.name == "nt", "exact Node and POSIX fixture executables are required")
class SeedsLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.distribution = self.root / "reviewed distribution"
        self.distribution.mkdir()
        (self.distribution / ".gitignore").write_text("IGNORED\n", encoding="utf-8")
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
        self.mise_environment = self.root / "mise-environment.jsonl"
        self.mise_config_listing = self.root / "mise-config-listing"
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
        self.node_executable = self.node_root / "bin" / "node"
        self.node_executable.parent.mkdir(parents=True)
        os.link(Path(NODE).resolve(), self.node_executable)
        environment_command = self._quote(str(shutil.which("env")))
        sort_command = self._quote(str(shutil.which("sort")))
        cat_command = self._quote(str(shutil.which("cat")))
        self._write_executable(
            self.bun_root / "bin" / "bun",
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = --version ]; then printf '1.3.10\\n'; exit 0; fi\n"
            f"printf '%s\\n' \"$*\" >> {self._quote(str(self.bun_log))}\n"
            "case \" $* \" in *\" --no-macros \"*) ;; *) exit 98 ;; esac\n"
            "case \" $* \" in *\" --tsconfig-override=\"*) ;; *) exit 97 ;; esac\n"
            f"{environment_command} | {sort_command} >> {self._quote(str(self.bun_log))}\n"
            f"if [ \"$({cat_command} {self._quote(str(self.bun_behavior))})\" = TERM ]; then kill -TERM $$; fi\n"
            f"exit \"$({cat_command} {self._quote(str(self.bun_behavior))})\"\n",
        )
        package = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli"
        package.mkdir(parents=True)
        (package / "package.json").write_bytes(SEEDS_PACKAGE_FIXTURE.read_bytes())
        (package / "src").mkdir()
        (package / "src" / "index.ts").write_text("console.log('fixture')\n", encoding="utf-8")
        (self.seeds_root / "bin").mkdir(parents=True)
        os.symlink("../lib/node_modules/@os-eco/seeds-cli/src/index.ts", self.seeds_root / "bin" / "sd")

    def _write_mise(self) -> None:
        self._write_executable(
            self.bin / "mise",
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> {self._quote(str(self.calls))}\n"
            f"printf '{{\"npm_config_registry\":\"%s\",\"npm_config_userconfig\":\"%s\",\"npm_config_globalconfig\":\"%s\",\"mise_global_config_file\":\"%s\",\"mise_system_config_file\":\"%s\",\"mise_override_config_filenames\":\"%s\",\"mise_no_env\":\"%s\",\"mise_no_hooks\":\"%s\",\"home\":\"%s\",\"cwd\":\"%s\"}}\\n' \"${{NPM_CONFIG_REGISTRY-}}\" \"${{NPM_CONFIG_USERCONFIG-}}\" \"${{NPM_CONFIG_GLOBALCONFIG-}}\" \"${{MISE_GLOBAL_CONFIG_FILE-}}\" \"${{MISE_SYSTEM_CONFIG_FILE-}}\" \"${{MISE_OVERRIDE_CONFIG_FILENAMES-}}\" \"${{MISE_NO_ENV-}}\" \"${{MISE_NO_HOOKS-}}\" \"${{HOME-}}\" \"$PWD\" >> {self._quote(str(self.mise_environment))}\n"
            f"if [ -f \"${{HOME-}}/ambient-mise-config-used\" ] || [ -f \"${{NPM_CONFIG_USERCONFIG-}}\" ] && grep -q hostile \"${{NPM_CONFIG_USERCONFIG-}}\"; then printf ambient >> {self._quote(str(self.mise_config_listing))}; fi\n"
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
        hostile_home = self.root / "hostile-home"
        hostile_home.mkdir(exist_ok=True)
        (hostile_home / ".npmrc").write_text("registry=https://home-hostile.invalid/\n", encoding="utf-8")
        (hostile_home / "ambient-mise-config-used").write_text("hostile\n", encoding="utf-8")
        hostile_npmrc = self.root / "hostile.npmrc"
        hostile_npmrc.write_text("registry=https://hostile.invalid/\n", encoding="utf-8")
        return os.environ | {
            "HOME": str(hostile_home),
            "PATH": str(self.bin) + os.pathsep + os.defpath,
            "XDG_STATE_HOME": str(self.state),
            "BUN_OPTIONS": "--inspect=127.0.0.1:9229",
            "BUN_INSPECT_PRELOAD": "hostile",
            "NODE_OPTIONS": "--trace-warnings",
            "NPM_CONFIG_REGISTRY": "https://hostile.invalid/",
            "NPM_CONFIG_USERCONFIG": str(hostile_npmrc),
            "MISE_GLOBAL_CONFIG_FILE": str(self.root / "hostile-mise.toml"),
            "MISE_OVERRIDE_CONFIG_FILENAMES": "hostile.toml",
            "MISE_DATA_DIR": str(self.root / "hostile-mise-data"),
            "SEEDS_DEBUG": "1",
        }

    def launcher(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.node_executable), str(LAUNCHER), *args],
            text=True,
            capture_output=True,
            env=env or self.environment(),
            check=False,
        )

    def bootstrap(self) -> subprocess.CompletedProcess[str]:
        return self.launcher("bootstrap", "--distribution", str(self.distribution))

    def active_receipt_path(self) -> Path:
        return self.state / "agentic-sdlc-orchestrator" / "seeds-runtime" / f"v{RECEIPT_SCHEMA}" / "active.json"

    def installed_launcher_path(self) -> Path:
        return self.active_receipt_path().parent / "seeds-launcher.mjs"

    def install_current_launcher(self) -> Path:
        installed = self.installed_launcher_path()
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(LAUNCHER.read_bytes())
        return installed

    def installed_launcher(self, *args: str, node: str | Path = NODE) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(node), str(self.installed_launcher_path()), *args],
            text=True,
            capture_output=True,
            env=self.environment(),
            check=False,
        )

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
        active = self.active_receipt_path()
        receipt = json.loads(active.read_text(encoding="utf-8"))
        self.assertEqual(receipt["tuple"]["node"]["version"], "22.22.3")
        self.assertEqual(receipt["tuple"]["bun"]["version"], "1.3.10")
        self.assertEqual(receipt["tuple"]["seeds"]["package"], "@os-eco/seeds-cli")
        self.assertEqual(receipt["tuple"]["seeds"]["bin"], "sd")
        self.assertIn("distribution", receipt["hashes"])
        self.assertTrue((active.parent / "trusted-bunfig.toml").is_file())
        self.assertEqual((active.parent / "trusted-bunfig.toml").read_bytes(), b"")
        self.assertEqual((active.parent / "trusted-tsconfig.json").read_bytes(), b"{}\n")
        mise_environments = [json.loads(line) for line in self.mise_environment.read_text(encoding="utf-8").splitlines()]
        for environment in mise_environments:
            self.assertEqual(environment["npm_config_registry"], "https://registry.npmjs.org/")
            self.assertNotEqual(environment["npm_config_userconfig"], environment["npm_config_globalconfig"])
            self.assertEqual(Path(environment["npm_config_userconfig"]).read_bytes(), b"")
            self.assertEqual(Path(environment["npm_config_globalconfig"]).read_bytes(), b"")
            self.assertEqual(Path(environment["mise_global_config_file"]), self.distribution / "mise.toml")
            self.assertEqual(environment["mise_system_config_file"], os.devnull)
            self.assertEqual(environment["mise_override_config_filenames"], "__agentic_sdlc_reviewed_config_only__")
            self.assertEqual(environment["mise_no_env"], "1")
            self.assertEqual(environment["mise_no_hooks"], "1")
            self.assertEqual(environment["home"], str(active.parent / "bootstrap-home"))
            self.assertEqual(environment["cwd"], environment["home"])
        self.assertFalse(self.mise_config_listing.exists())
        second = self.bootstrap()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((active.parent / "previous.json").is_file())

    def test_bootstrap_git_probes_ignore_repository_global_system_config_and_hooks(self) -> None:
        marker = self.root / "git-execution-marker"
        probe = self.root / "git-probe"
        self._write_executable(
            probe,
            "#!/bin/sh\n"
            f"printf executed >> {self._quote(str(marker))}\n"
            "cat\n",
        )
        local_hooks = self.distribution / ".git" / "local-hooks"
        local_hooks.mkdir()
        shutil.copy2(probe, local_hooks / "post-index-change")
        (local_hooks / "post-index-change").chmod(probe.stat().st_mode)
        (self.distribution / ".gitattributes").write_text("mise.toml filter=hostile\n", encoding="utf-8")
        self._run(["git", "add", ".gitattributes"], cwd=self.distribution)
        self._run(["git", "commit", "-qm", "attribute fixture"], cwd=self.distribution)
        self._run(["git", "config", "core.fsmonitor", str(probe)], cwd=self.distribution)
        self._run(["git", "config", "core.hooksPath", str(local_hooks)], cwd=self.distribution)
        self._run(["git", "config", "core.worktree", str(self.root / "hostile-worktree")], cwd=self.distribution)
        self._run(["git", "config", "filter.hostile.clean", str(probe)], cwd=self.distribution)

        global_config = self.root / "hostile-global-gitconfig"
        global_config.write_text(
            f"[core]\n\tfsmonitor = {probe}\n\thooksPath = {local_hooks}\n",
            encoding="utf-8",
        )
        system_config = self.root / "hostile-system-gitconfig"
        system_config.write_text(global_config.read_text(encoding="utf-8"), encoding="utf-8")
        hostile = self.environment() | {
            "GIT_CONFIG_GLOBAL": str(global_config),
            "GIT_CONFIG_SYSTEM": str(system_config),
            "GIT_CONFIG_NOSYSTEM": "0",
        }
        marker.unlink(missing_ok=True)

        result = self.launcher("bootstrap", "--distribution", str(self.distribution), env=hostile)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists(), "Git admission must not execute config- or hook-selected programs")

    def test_bootstrap_rejects_nested_dirty_and_untracked_distribution_trees(self) -> None:
        nested = self.distribution / "nested"
        nested.mkdir()
        shutil.copy2(self.distribution / "mise.toml", nested / "mise.toml")
        shutil.copy2(self.distribution / "mise.lock", nested / "mise.lock")
        nested_result = self.launcher("bootstrap", "--distribution", str(nested))
        self.assertNotEqual(nested_result.returncode, 0)
        self.assertIn("Git root", nested_result.stderr)

        shutil.rmtree(nested)
        (self.distribution / "mise.toml").write_text("[tools]\nnode = '22.22.4'\n", encoding="utf-8")
        dirty = self.bootstrap()
        self.assertNotEqual(dirty.returncode, 0)
        self.assertIn("clean Git tree", dirty.stderr)

        self._run(["git", "restore", "mise.toml"], cwd=self.distribution)
        (self.distribution / "UNREVIEWED").write_text("untracked\n", encoding="utf-8")
        untracked = self.bootstrap()
        self.assertNotEqual(untracked.returncode, 0)
        self.assertIn("untracked", untracked.stderr)

        (self.distribution / "UNREVIEWED").unlink()
        (self.distribution / "IGNORED").write_text("ignored\n", encoding="utf-8")
        ignored = self.bootstrap()
        self.assertNotEqual(ignored.returncode, 0)
        self.assertIn("ignored", ignored.stderr)
        self.assertFalse(self.active_receipt_path().exists())

    @unittest.skipIf(HOSTILE_NODE is None, "a non-22.22.3 Node is required for interpreter rejection fixture")
    def test_bootstrap_and_inspect_reject_launcher_process_running_under_wrong_node(self) -> None:
        result = subprocess.run(
            [HOSTILE_NODE, str(LAUNCHER), "bootstrap", "--distribution", str(self.distribution)],
            text=True,
            capture_output=True,
            env=self.environment(),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("launcher Node version mismatch", result.stderr)

        self.assertEqual(self.bootstrap().returncode, 0)
        inspect = subprocess.run(
            [HOSTILE_NODE, str(LAUNCHER), "inspect", "--target", str(self.target), "prime"],
            text=True,
            capture_output=True,
            env=self.environment(),
            check=False,
        )
        self.assertNotEqual(inspect.returncode, 0)
        self.assertIn("launcher Node version mismatch", inspect.stderr)

    def test_bootstrap_rejects_package_execution_controls_before_receipt_publication(self) -> None:
        package = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli" / "package.json"
        metadata = json.loads(SEEDS_PACKAGE_FIXTURE.read_text(encoding="utf-8"))
        for control in (
            {"preload": ["hostile"]},
            {"bun": {"preload": ["hostile"]}},
            {"engines": {"bun": {"preload": ["hostile"]}}},
            {"nested": {"bun": "hostile"}},
            {"nested": {"macro": "hostile"}},
        ):
            with self.subTest(control=control):
                package.write_text(json.dumps(metadata | control) + "\n", encoding="utf-8")
                result = self.bootstrap()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("execution control", result.stderr)
                self.assertFalse(self.active_receipt_path().exists())

    def test_bootstrap_rejects_recursively_nested_package_control_files(self) -> None:
        package = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli"
        controls = (
            "src/bunfig.toml",
            "src/bunfig.json",
            "src/tsconfig.json",
            "src/jsconfig.json",
            "src/deeper/macro.ts",
            "src/deeper/macros.ts",
            "src/deeper/preload.ts",
            "src/deeper/preload.js",
        )
        for relative_control in controls:
            with self.subTest(control=relative_control):
                control = package / relative_control
                control.parent.mkdir(parents=True, exist_ok=True)
                control.write_text("{}\n", encoding="utf-8")
                result = self.bootstrap()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("execution control", result.stderr)
                self.assertFalse(self.active_receipt_path().exists())
                control.unlink()
                while control.parent != package and not any(control.parent.iterdir()):
                    parent = control.parent
                    parent.rmdir()
                    control = parent

    def test_bootstrap_rejects_nested_package_metadata_and_symlink_controls(self) -> None:
        package = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli"
        nested_metadata = package / "src" / "package.json"
        nested_metadata.write_text('{"bun":{"preload":["./hostile.ts"]}}\n', encoding="utf-8")
        metadata_result = self.bootstrap()
        self.assertNotEqual(metadata_result.returncode, 0)
        self.assertIn("execution control", metadata_result.stderr)
        self.assertFalse(self.active_receipt_path().exists())
        nested_metadata.unlink()

        symlink_control = package / "src" / "preload.ts"
        os.symlink("index.ts", symlink_control)
        symlink_result = self.bootstrap()
        self.assertNotEqual(symlink_result.returncode, 0)
        self.assertIn("execution control", symlink_result.stderr)
        self.assertFalse(self.active_receipt_path().exists())

    def test_inspect_uses_receipt_never_mise_and_filters_environment_before_exact_bun(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        before = self.calls.read_text(encoding="utf-8")
        result = self.launcher("inspect", "--target", str(self.target), "ready", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), before)
        contents = self.bun_log.read_text(encoding="utf-8")
        self.assertIn("--config=", contents)
        self.assertIn("--tsconfig-override=", contents)
        self.assertIn("--no-macros", contents)
        self.assertIn("--no-env-file --no-install", contents)
        self.assertIn("ready --format json", contents)
        self.assertIn(f"PWD={self.target}", contents)
        for hostile in ("BUN_OPTIONS=", "BUN_INSPECT_PRELOAD=", "NODE_OPTIONS=", "NPM_CONFIG_REGISTRY=", "MISE_DATA_DIR=", "SEEDS_DEBUG="):
            self.assertNotIn(hostile, contents)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", contents)

    def test_inspect_uses_only_finite_read_only_git_adapter(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        receipt = json.loads(self.active_receipt_path().read_text(encoding="utf-8"))
        adapter = Path(receipt["tuple"]["trusted"]["gitAdapter"])
        self.assertTrue(adapter.is_file())
        self.assertEqual(adapter.parent, self.active_receipt_path().parent)
        self.assertNotEqual(adapter.parent, Path(receipt["tuple"]["git"]["path"]).parent)

        for argv in (("rev-parse", "--git-dir"), ("rev-parse", "--git-common-dir")):
            with self.subTest(argv=argv):
                allowed = subprocess.run([adapter, *argv], cwd=self.distribution, text=True, capture_output=True, check=False)
                self.assertEqual(allowed.returncode, 0, allowed.stderr)
        for argv in (("status",), ("rev-parse", "HEAD"), ("rev-parse", "--show-toplevel"), ("rev-parse", "--git-dir", "extra")):
            with self.subTest(argv=argv):
                denied = subprocess.run([adapter, *argv], cwd=self.distribution, text=True, capture_output=True, check=False)
                self.assertNotEqual(denied.returncode, 0)

    def test_inspect_rejects_trusted_git_adapter_drift_before_bun(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        receipt = json.loads(self.active_receipt_path().read_text(encoding="utf-8"))
        adapter = Path(receipt["tuple"]["trusted"]["gitAdapter"])
        adapter.write_text(adapter.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        rejected = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("Git adapter", rejected.stderr)
        self.assertFalse(self.bun_log.exists())

    def test_inspect_rejects_missing_partial_drifted_receipt_and_invalid_grammar_before_bun(self) -> None:
        missing = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse(self.bun_log.exists())
        self.assertEqual(self.bootstrap().returncode, 0)
        active = self.active_receipt_path()
        active.write_text(f'{{"schema":{RECEIPT_SCHEMA}}}\n', encoding="utf-8")
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

    def test_inspect_binds_executing_node_to_recorded_exact_binary_and_hash(self) -> None:
        self.install_current_launcher()
        bootstrap = self.installed_launcher("bootstrap", "--distribution", str(self.distribution), node=self.node_executable)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

        wrong_same_version = self.root / "wrong-node" / "bin" / "node"
        wrong_same_version.parent.mkdir(parents=True)
        shutil.copy2(Path(NODE).resolve(), wrong_same_version)
        wrong_same_version.chmod(wrong_same_version.stat().st_mode | stat.S_IXUSR)
        inspect = self.installed_launcher("inspect", "--target", str(self.target), "prime", node=wrong_same_version)
        self.assertNotEqual(inspect.returncode, 0)
        self.assertIn("executing Node", inspect.stderr)
        self.assertFalse(self.bun_log.exists())

    def test_receipt_has_closed_distribution_shape_and_binds_installed_launcher(self) -> None:
        installed = self.install_current_launcher()
        bootstrap = self.installed_launcher("bootstrap", "--distribution", str(self.distribution), node=self.node_executable)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
        active = self.active_receipt_path()
        pristine = json.loads(active.read_text(encoding="utf-8"))
        distribution = pristine["distribution"]
        self.assertEqual(
            set(distribution),
            {"root", "commit", "gitTree", "tree", "miseToml", "miseLock", "launcher", "launcherHash"},
        )
        self.assertEqual(pristine["hashes"]["nodeExecutable"], sha256(self.node_executable.read_bytes()).hexdigest())
        self.assertEqual(pristine["runtime"]["node"], str(self.node_executable.resolve()))
        self.assertEqual(pristine["runtime"]["nodeHash"], pristine["hashes"]["nodeExecutable"])
        self.assertEqual(Path(distribution["launcher"]), installed.resolve())
        self.assertEqual(distribution["launcherHash"], sha256(installed.read_bytes()).hexdigest())

    def test_inspect_rejects_open_or_partial_distribution_provenance(self) -> None:
        self.install_current_launcher()
        bootstrap = self.installed_launcher("bootstrap", "--distribution", str(self.distribution), node=self.node_executable)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
        active = self.active_receipt_path()
        pristine = json.loads(active.read_text(encoding="utf-8"))
        mutations = (
            lambda receipt: receipt.pop("distribution"),
            lambda receipt: receipt.pop("runtime"),
            lambda receipt: receipt["hashes"]["distribution"].pop("gitTree"),
            lambda receipt: receipt["distribution"].__setitem__("extra", "forged"),
            lambda receipt: receipt["hashes"].pop("distribution"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                if self.bun_log.exists():
                    self.bun_log.unlink()
                receipt = json.loads(json.dumps(pristine))
                mutate(receipt)
                active.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
                rejected = self.installed_launcher("inspect", "--target", str(self.target), "prime", node=self.node_executable)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn("partial or invalid", rejected.stderr)
                self.assertFalse(self.bun_log.exists())

    def test_inspect_rejects_current_installed_launcher_hash_drift(self) -> None:
        installed = self.install_current_launcher()
        bootstrap = self.installed_launcher("bootstrap", "--distribution", str(self.distribution), node=self.node_executable)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
        installed.write_text(installed.read_text(encoding="utf-8") + "\n// drift\n", encoding="utf-8")
        drift = self.installed_launcher("inspect", "--target", str(self.target), "prime", node=self.node_executable)
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("launcher", drift.stderr)
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


@unittest.skipUnless(os.name == "nt", "native Windows launcher fixture")
class NativeWindowsSeedsLauncherTests(unittest.TestCase):
    def test_real_locked_tuple_bootstraps_and_inspects_with_hostile_ambient_config(self) -> None:
        mise = shutil.which("mise.exe") or shutil.which("mise")
        git = shutil.which("git.exe") or shutil.which("git")
        self.assertIsNotNone(mise, "native Windows mise is required")
        self.assertIsNotNone(git, "native Windows Git is required")
        node_root = subprocess.run(
            [mise, "--no-config", "where", "node@22.22.3"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        bun_root = subprocess.run(
            [mise, "--no-config", "where", "bun@1.3.10"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        exact_node = Path(node_root) / "node.exe"
        exact_bun = Path(bun_root) / "bin" / "bun.exe"
        self.assertTrue(exact_node.is_file(), "exact Node 22.22.3 must be installed for the native fixture")
        self.assertTrue(exact_bun.is_file(), "exact Bun 1.3.10 must be installed for the native fixture")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            distribution = root / "reviewed distribution"
            distribution.mkdir()
            shutil.copy2(ROOT / "mise.toml", distribution / "mise.toml")
            shutil.copy2(ROOT / "mise.lock", distribution / "mise.lock")
            subprocess.run(["git", "init", "-q"], cwd=distribution, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=distribution, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=distribution, check=True)
            subprocess.run(["git", "add", "."], cwd=distribution, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=distribution, check=True)
            recorded_git_log = root / "recorded-git.jsonl"
            recorded_git = root / "recorded-git" / "git.exe"
            recorded_git.parent.mkdir()
            recorded_git_source = root / "recorded-git.ts"
            recorded_git_source.write_text(
                "import{appendFileSync,readFileSync}from'node:fs';"
                "const args=process.argv.slice(2);"
                f"const log={json.dumps(str(recorded_git_log))};"
                "const input=args[0]==='hash-object'?readFileSync(0):undefined;"
                "const child=Bun.spawnSync(["
                f"{json.dumps(str(Path(git).resolve()))},...args],"
                "{cwd:process.cwd(),env:process.env,...(input===undefined?{}:{stdin:input})});"
                "appendFileSync(log,JSON.stringify({args,exitCode:child.exitCode,stderr:child.stderr.toString(),searchControl:process.env.NoDefaultCurrentDirectoryInExePath??null})+'\\n');"
                "process.stdout.write(child.stdout);process.stderr.write(child.stderr);process.exit(child.exitCode??1);\n",
                encoding="utf-8",
            )
            recorded_git_compile = subprocess.run(
                [
                    exact_bun,
                    "build",
                    "--compile",
                    f"--compile-executable-path={exact_bun}",
                    "--no-compile-autoload-dotenv",
                    "--no-compile-autoload-bunfig",
                    "--no-compile-autoload-tsconfig",
                    "--no-compile-autoload-package-json",
                    f"--outfile={recorded_git}",
                    recorded_git_source,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                env={"SystemRoot": os.environ["SystemRoot"]},
                check=False,
                timeout=300,
            )
            self.assertEqual(recorded_git_compile.returncode, 0, recorded_git_compile.stderr)
            target = root / "hostile target"
            target.mkdir()
            (target / "bunfig.toml").write_text("preload = ['./hostile.ts']\n", encoding="utf-8")
            hostile_npmrc = root / "hostile.npmrc"
            hostile_npmrc.write_text("registry=https://hostile.invalid/\n", encoding="utf-8")
            state = root / "state"
            environment = os.environ | {
                "PATH": os.pathsep.join((str(Path(mise).parent), str(recorded_git.parent))),
                "LOCALAPPDATA": str(state),
                "HOME": str(target),
                "USERPROFILE": str(target),
                "NPM_CONFIG_REGISTRY": "https://hostile.invalid/",
                "NPM_CONFIG_USERCONFIG": str(hostile_npmrc),
                "BUN_OPTIONS": "--inspect=127.0.0.1:9229",
                "NODE_OPTIONS": "--trace-warnings",
                "MISE_GLOBAL_CONFIG_FILE": str(root / "hostile-mise.toml"),
            }
            bootstrapped = subprocess.run(
                [exact_node, LAUNCHER, "bootstrap", "--distribution", distribution],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
                timeout=300,
            )
            self.assertEqual(
                bootstrapped.returncode,
                0,
                f"{bootstrapped.stderr}\nrecorded Git: {recorded_git_log.read_text(encoding='utf-8') if recorded_git_log.exists() else 'none'}",
            )
            inspected = subprocess.run(
                [exact_node, LAUNCHER, "inspect", "--target", target, "--version"],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
                timeout=60,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(inspected.stdout.strip(), "0.5.14")
            receipt = json.loads(
                (state / "agentic-sdlc-orchestrator" / "seeds-runtime" / f"v{RECEIPT_SCHEMA}" / "active.json").read_text(encoding="utf-8")
            )
            self.assertTrue(os.path.samefile(receipt["tuple"]["git"]["path"], recorded_git))
            recorded_git_log.unlink(missing_ok=True)
            seeds_dir = distribution / ".seeds"
            seeds_dir.mkdir()
            (seeds_dir / "config.yaml").write_text("project: fixture\nversion: '1'\n", encoding="utf-8")
            prime_content = "WINDOWS-ADAPTER-PRIME\n"
            (seeds_dir / "PRIME.md").write_text(prime_content, encoding="utf-8")
            hostile_marker = root / "target-git-executed"
            hostile_source = root / "hostile-git.ts"
            hostile_source.write_text(
                f"await Bun.write({json.dumps(str(hostile_marker))}, 'executed');"
                "process.stdout.write('.git\\n');\n",
                encoding="utf-8",
            )
            hostile_git = distribution / "git.exe"
            compiled = subprocess.run(
                [
                    receipt["tuple"]["bun"]["executable"],
                    f'--config={receipt["tuple"]["trusted"]["bunfig"]}',
                    "--no-env-file",
                    "--no-install",
                    "--no-macros",
                    f'--tsconfig-override={receipt["tuple"]["trusted"]["tsconfig"]}',
                    "build",
                    "--compile",
                    f'--compile-executable-path={receipt["tuple"]["bun"]["executable"]}',
                    "--no-compile-autoload-dotenv",
                    "--no-compile-autoload-bunfig",
                    "--no-compile-autoload-tsconfig",
                    "--no-compile-autoload-package-json",
                    f"--outfile={hostile_git}",
                    hostile_source,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                env={"SystemRoot": os.environ["SystemRoot"]},
                check=False,
                timeout=300,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            hostile_com = distribution / "git.com"
            shutil.copy2(hostile_git, hostile_com)
            adapter = Path(receipt["tuple"]["trusted"]["gitAdapter"])
            adapter_probe = root / "adapter-probe.ts"
            adapter_probe.write_text(
                'const target=process.argv[2];'
                'const allowed=Bun.spawnSync(["git","rev-parse","--git-dir"],{cwd:target,env:process.env});'
                'const denied=Bun.spawnSync(["git","status"],{cwd:target,env:process.env});'
                'if(allowed.exitCode!==0||allowed.stdout.toString().trim()!==".git"||denied.exitCode===0)process.exit(1);\n',
                encoding="utf-8",
            )
            adapter_environment = {
                "PATH": str(adapter.parent),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_SYSTEM": "NUL",
                "GIT_CONFIG_GLOBAL": receipt["tuple"]["trusted"]["gitconfig"],
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "PATHEXT": ".EXE",
                "SystemRoot": os.environ["SystemRoot"],
            }
            probe_command = [
                receipt["tuple"]["bun"]["executable"],
                f'--config={receipt["tuple"]["trusted"]["bunfig"]}',
                "--no-macros",
                "--no-env-file",
                "--no-install",
                f'--tsconfig-override={receipt["tuple"]["trusted"]["tsconfig"]}',
                adapter_probe,
                distribution,
            ]
            adapter_result = subprocess.run(
                probe_command,
                cwd=distribution,
                text=True,
                capture_output=True,
                env=adapter_environment,
                check=False,
                timeout=60,
            )
            self.assertEqual(adapter_result.returncode, 0, adapter_result.stderr)
            self.assertFalse(hostile_marker.exists(), "the closed runtime environment must select the receipt-bound adapter")
            direct_hostile = subprocess.run(
                [hostile_git, "rev-parse", "--git-dir"],
                cwd=distribution,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(direct_hostile.returncode, 0, direct_hostile.stderr)
            self.assertTrue(hostile_marker.exists(), "the target-local hostile executable must be runnable")
            hostile_marker.unlink()
            recorded_git_log.unlink()
            prime = subprocess.run(
                [exact_node, LAUNCHER, "inspect", "--target", distribution, "prime"],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
                timeout=60,
            )
            self.assertEqual(prime.returncode, 0, prime.stderr)
            self.assertEqual(prime.stdout, prime_content)
            self.assertFalse(hostile_marker.exists(), "inspect must not execute target-local git.exe or git.com")
            successful_calls = [json.loads(line) for line in recorded_git_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(
                [call["args"] for call in successful_calls],
                [
                    ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=NUL", "rev-parse", "--git-common-dir"],
                ],
            )
            self.assertTrue(all(call["exitCode"] == 0 for call in successful_calls))
            self.assertTrue(all(call["stderr"] == "" for call in successful_calls))
            self.assertTrue(all(call["searchControl"] == "1" for call in successful_calls))
            recorded_git_log.unlink()
            non_repository = root / "non-repository"
            non_repository_seeds = non_repository / ".seeds"
            non_repository_seeds.mkdir(parents=True)
            (non_repository_seeds / "config.yaml").write_text("project: outside\nversion: '1'\n", encoding="utf-8")
            outside_content = "OUTSIDE-PRIME\n"
            (non_repository_seeds / "PRIME.md").write_text(outside_content, encoding="utf-8")
            outside_prime = subprocess.run(
                [exact_node, LAUNCHER, "inspect", "--target", non_repository, "prime"],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
                timeout=60,
            )
            self.assertEqual(outside_prime.returncode, 0, outside_prime.stderr)
            self.assertEqual(outside_prime.stdout, outside_content)
            failed_call = json.loads(recorded_git_log.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(
                failed_call["args"],
                ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=NUL", "rev-parse", "--git-common-dir"],
            )
            self.assertNotEqual(failed_call["exitCode"], 0)
            self.assertIn("not a git repository", failed_call["stderr"])
            self.assertEqual(failed_call["searchControl"], "1")
            self.assertFalse(hostile_marker.exists())
            for flag in ("--git-dir", "--git-common-dir"):
                with self.subTest(flag=flag):
                    direct = subprocess.run(
                        [adapter, "rev-parse", flag],
                        cwd=distribution,
                        text=True,
                        capture_output=True,
                        env=adapter_environment,
                        check=False,
                        timeout=60,
                    )
                    self.assertEqual(direct.returncode, 0, direct.stderr)
                    self.assertEqual(direct.stdout.strip(), ".git")
            git_failure = subprocess.run(
                [adapter, "rev-parse", "--git-dir"],
                cwd=root,
                text=True,
                capture_output=True,
                env=adapter_environment,
                check=False,
                timeout=60,
            )
            self.assertNotEqual(git_failure.returncode, 0)
            self.assertIn("not a git repository", git_failure.stderr)
            hostile_git.unlink()
            hostile_com.unlink()
            shutil.rmtree(seeds_dir)
            adapter_before = adapter.read_bytes()
            second_bootstrap = subprocess.run(
                [exact_node, LAUNCHER, "bootstrap", "--distribution", distribution],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
                timeout=300,
            )
            self.assertEqual(second_bootstrap.returncode, 0, second_bootstrap.stderr)
            self.assertEqual(adapter.read_bytes(), adapter_before)
            stale_build = Path(receipt["tuple"]["trusted"]["gitAdapter"]).parent / "git-adapter-build"
            stale_build.mkdir()
            stale_bootstrap = subprocess.run(
                [exact_node, LAUNCHER, "bootstrap", "--distribution", distribution],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
                timeout=300,
            )
            self.assertNotEqual(stale_bootstrap.returncode, 0)
            self.assertIn("build directory already exists", stale_bootstrap.stderr)
            self.assertEqual(receipt["platform"], "win32")
            self.assertTrue(receipt["tuple"]["node"]["executable"].lower().endswith("node.exe"))
            self.assertTrue(receipt["tuple"]["bun"]["executable"].lower().endswith("bun.exe"))
            self.assertTrue(receipt["tuple"]["seeds"]["packageRoot"].lower().endswith("@os-eco\\seeds-cli"))


if __name__ == "__main__":
    unittest.main()
