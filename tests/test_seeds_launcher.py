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
LAUNCHER = ROOT / "skills" / "agentic-sdlc" / "tools" / "seeds-launcher.mjs"
SEEDS_PACKAGE_FIXTURE = ROOT / "tests" / "fixtures" / "seeds-cli-0.5.15" / "package.json"
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
        and subprocess.run([candidate, "--version"], text=True, capture_output=True, check=False).stdout.strip().removeprefix("v") != "22.23.2"
    ),
    None,
)
EXACT_NODE = Path(
    os.environ.get(
        "AGENTIC_SDLC_TEST_NODE",
        str(Path.home() / ".local" / "share" / "mise" / "installs" / "node" / "22.23.2" / ("node.exe" if os.name == "nt" else "bin/node")),
    )
)
NODE = str(EXACT_NODE) if EXACT_NODE.is_file() else HOST_NODE
RECEIPT_SCHEMA = 2
# The exact tuple this repository pinned before the 2026-08-20 bump, which is what a real receipt
# published by the previous launcher records once the constants move forward.
SUPERSEDED_NODE = "22.22.3"
SUPERSEDED_BUN = "1.3.10"
SUPERSEDED_SEEDS = "0.5.14"


class LauncherFixture:
    """The hermetic tool layout, fake mise, and hostile ambient environment every launcher
    suite runs against."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        # RESOLVED ONCE, HERE, so every fixture path below is the same spelling the launcher and its
        # children report back. On macOS `$TMPDIR` lives under `/var/folders/...` and `/var` is a
        # symlink to `/private/var`: `mkdtemp()` returns the unresolved form, while the launcher
        # canonicalizes with `realpathSync` and the fake tools' `env` dump carries a `PWD` that came
        # from getcwd. Comparing the two fails on paths the launcher never got wrong -- the receipt's
        # `mise_global_config_file`, `bootstrap-home`, the trusted Git adapter's directory, and the
        # child `PWD=` line. Resolving the root fixes all of them at the source; symlinks the tests
        # deliberately create UNDER this root are unaffected, because they do not exist yet.
        self.root = Path(self.temporary.name).resolve()
        self.distribution = self.root / "reviewed distribution"
        self.distribution.mkdir()
        (self.distribution / ".gitignore").write_text("IGNORED\n", encoding="utf-8")
        (self.distribution / "mise.toml").write_text("[tools]\nnode = '22.23.2'\n", encoding="utf-8")
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
        # A stand-in queue writer the record fixtures install to model exact and divergent
        # queue effects; absent, the fake Bun keeps its original inspect behavior.
        self.queue_writer = self.root / "queue-writer"
        self.node_root = self.root / "installs" / "node" / "22.23.2"
        self.bun_root = self.root / "installs" / "bun" / "1.4.0"
        self.seeds_root = self.root / "installs" / "npm-os-eco-seeds-cli" / "0.5.15"
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
            "if [ \"${1:-}\" = --version ]; then printf '1.4.0\\n'; exit 0; fi\n"
            f"printf '%s\\n' \"$*\" >> {self._quote(str(self.bun_log))}\n"
            "case \" $* \" in *\" --no-macros \"*) ;; *) exit 98 ;; esac\n"
            "case \" $* \" in *\" --tsconfig-override=\"*) ;; *) exit 97 ;; esac\n"
            f"{environment_command} | {sort_command} >> {self._quote(str(self.bun_log))}\n"
            f"if [ -x {self._quote(str(self.queue_writer))} ]; then {self._quote(str(self.queue_writer))} \"$@\"; exit $?; fi\n"
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
            f"    node@22.23.2) printf '%s\\n' {self._quote(str(self.node_root))} ;;\n"
            f"    bun@1.4.0) printf '%s\\n' {self._quote(str(self.bun_root))} ;;\n"
            f"    npm:@os-eco/seeds-cli@0.5.15) printf '%s\\n' {self._quote(str(self.seeds_root))} ;;\n"
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
        return self.state / "agentic-sdlc" / "seeds-runtime" / f"v{RECEIPT_SCHEMA}" / "active.json"

    def write_superseded_tuple_receipt(self) -> dict:
        """Leave behind exactly what a pin bump leaves behind: the receipt the launcher published,
        still structurally intact and internally consistent, recording the PREVIOUS tuple."""
        active = self.active_receipt_path()
        receipt = json.loads(active.read_text(encoding="utf-8"))
        receipt["tuple"]["node"]["version"] = SUPERSEDED_NODE
        receipt["tuple"]["bun"]["version"] = SUPERSEDED_BUN
        receipt["tuple"]["seeds"]["version"] = SUPERSEDED_SEEDS
        active.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt

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


@unittest.skipIf(NODE is None or os.name == "nt", "exact Node and POSIX fixture executables are required")
class SeedsLauncherTests(LauncherFixture, unittest.TestCase):
    def test_bootstrap_is_locked_validates_exact_tuple_and_publishes_active_prior_receipts(self) -> None:
        first = self.bootstrap()
        self.assertEqual(first.returncode, 0, first.stderr)
        calls = self.calls.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls[0], "--locked install")
        self.assertEqual(calls[1:], [
            "--no-config where node@22.23.2",
            "--no-config where bun@1.4.0",
            "--no-config where npm:@os-eco/seeds-cli@0.5.15",
        ])
        active = self.active_receipt_path()
        receipt = json.loads(active.read_text(encoding="utf-8"))
        self.assertEqual(receipt["tuple"]["node"]["version"], "22.23.2")
        self.assertEqual(receipt["tuple"]["bun"]["version"], "1.4.0")
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

    def test_bootstrap_supersedes_a_structurally_intact_prior_tuple_receipt(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        active = self.active_receipt_path()
        retained = active.parent / "previous.json"
        self.assertFalse(retained.exists())
        obsolete = self.write_superseded_tuple_receipt()

        # The wedge this covers: a pin bump leaves a receipt whose recorded tuple CANNOT equal the
        # new launcher's constants, and bootstrap is the one verb whose job is to establish a tuple,
        # so it retains the predecessor and publishes instead of refusing at validate-before-retain.
        upgrade = self.bootstrap()
        self.assertEqual(upgrade.returncode, 0, upgrade.stderr)
        self.assertIn("superseded prior tuple receipt", upgrade.stdout)
        self.assertIn(f'node "{SUPERSEDED_NODE}"', upgrade.stdout)
        self.assertIn(f'bun "{SUPERSEDED_BUN}"', upgrade.stdout)
        self.assertIn(f'"{SUPERSEDED_SEEDS}"', upgrade.stdout)
        self.assertIn(str(retained), upgrade.stdout)
        self.assertEqual(json.loads(retained.read_text(encoding="utf-8")), obsolete, "the obsolete receipt is the rollback predecessor, byte for byte")
        published = json.loads(active.read_text(encoding="utf-8"))
        self.assertEqual(published["tuple"]["node"]["version"], "22.23.2")
        self.assertEqual(published["tuple"]["bun"]["version"], "1.4.0")
        self.assertEqual(published["tuple"]["seeds"]["version"], "0.5.15")

        # Positive control: an ordinary same-tuple re-bootstrap still succeeds, still retains its
        # predecessor, and prints NO supersession line -- so that line is evidence of an actual
        # tuple change rather than a banner every bootstrap emits.
        again = self.bootstrap()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotIn("superseded", again.stdout)
        self.assertEqual(json.loads(retained.read_text(encoding="utf-8")), published)

        # C1 escaping: a recorded tuple field carrying a raw C1 byte (U+009B) must render escaped
        # in the supersession line, never as the raw byte, so no receipt field can inject or
        # terminate a line of this launcher's stdout. JSON.stringify alone does not escape this
        # range -- only rendered()'s explicit .replace does -- so this exercises that pass directly.
        with self.subTest(seeds_version="C1 byte"):
            c1_active = json.loads(active.read_text(encoding="utf-8"))
            c1_active["tuple"]["seeds"]["version"] = "0.5.14\u009b"
            active.write_text(json.dumps(c1_active, indent=2) + "\n", encoding="utf-8")
            c1_upgrade = self.bootstrap()
            self.assertEqual(c1_upgrade.returncode, 0, c1_upgrade.stderr)
            self.assertIn("superseded prior tuple receipt", c1_upgrade.stdout)
            # Positive control: the plain, unescaped prefix is still visible, so the assertion
            # below is about the C1 byte specifically and not about the whole field vanishing.
            self.assertIn("0.5.14", c1_upgrade.stdout)
            self.assertIn('"0.5.14\\u009b"', c1_upgrade.stdout)
            self.assertNotIn("\u009b", c1_upgrade.stdout)

    def test_bootstrap_still_refuses_a_prior_receipt_that_fails_its_own_validation(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        active = self.active_receipt_path()
        retained = active.parent / "previous.json"
        pristine = json.loads(active.read_text(encoding="utf-8"))
        corruptions = (
            # Closed key sets and internal cross-references are untouched by the relaxation: only
            # the tuple-version comparison against the current constants moved.
            lambda receipt: receipt["distribution"].pop("gitTree"),
            lambda receipt: receipt["distribution"].__setitem__("extra", "forged"),
            lambda receipt: receipt["runtime"].__setitem__("launcherHash", "0" * 64),
            lambda receipt: receipt["distribution"].__setitem__("commit", "b" * 40),
            lambda receipt: receipt["hashes"]["distribution"].pop("commit"),
            lambda receipt: receipt.__setitem__("schema", RECEIPT_SCHEMA + 1),
            # Supplied-but-blank is not the same fact as a superseded version: an empty string is
            # malformed in both modes, so the relaxed comparison can never admit one.
            lambda receipt: receipt["tuple"]["node"].__setitem__("version", ""),
            lambda receipt: receipt["tuple"]["bun"].__setitem__("version", ""),
            lambda receipt: receipt["tuple"]["seeds"].__setitem__("version", ""),
            lambda receipt: receipt["tuple"]["seeds"].__setitem__("package", ""),
            lambda receipt: receipt["tuple"]["seeds"].__setitem__("bin", ""),
            # Not supplied at all is a different fact again, and it breaks the closed key set.
            lambda receipt: receipt["tuple"]["node"].pop("version"),
            lambda receipt: receipt["tuple"]["seeds"].pop("bin"),
            # A non-string version is neither current nor superseded.
            lambda receipt: receipt["tuple"]["node"].__setitem__("version", 22.232),
            lambda receipt: receipt["tuple"]["bun"].__setitem__("version", None),
        )
        for corrupt in corruptions:
            with self.subTest(corrupt=corrupt):
                receipt = json.loads(json.dumps(pristine))
                corrupt(receipt)
                active.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
                refused = self.bootstrap()
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("partial or invalid", refused.stderr)
                self.assertFalse(retained.exists(), "a refused predecessor is never retained as rollback material")
                self.assertEqual(json.loads(active.read_text(encoding="utf-8")), receipt, "the refusal leaves the receipt exactly as it found it")
        # Positive control: the same fixture bootstraps cleanly the moment the predecessor is well
        # formed again, so the refusals above are about the receipt and not about the fixture.
        active.write_text(json.dumps(pristine) + "\n", encoding="utf-8")
        recovered = self.bootstrap()
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertTrue(retained.is_file())

    def test_inspect_and_record_still_refuse_a_superseded_tuple_receipt(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        # Positive control first: the pristine receipt really does run, so the refusals below are
        # about the recorded tuple rather than a fixture that never worked.
        admitted = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertEqual(admitted.returncode, 0, admitted.stderr)
        self.assertTrue(self.bun_log.exists())
        self.bun_log.unlink()

        self.write_superseded_tuple_receipt()
        refused = self.launcher("inspect", "--target", str(self.target), "prime")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("partial or invalid", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        # The conductor's write seam inherits every inspect admission: only bootstrap gained the
        # supersede path, because only bootstrap establishes a tuple.
        writer = self.launcher("record", "--target", str(self.target), "--queue-writer", "conductor", "--expect-queue", "absent", "init")
        self.assertNotEqual(writer.returncode, 0)
        self.assertIn("partial or invalid", writer.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse((self.target / ".seeds").exists())

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

    @unittest.skipIf(HOSTILE_NODE is None, "a non-22.23.2 Node is required for interpreter rejection fixture")
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

        for argv in (
            ("rev-parse", "--git-dir"),
            ("rev-parse", "--git-common-dir"),
            ("rev-parse", "--verify", "HEAD^{commit}"),
        ):
            with self.subTest(argv=argv):
                allowed = subprocess.run([adapter, *argv], cwd=self.distribution, text=True, capture_output=True, check=False)
                self.assertEqual(allowed.returncode, 0, allowed.stderr)
        for argv in (("status",), ("rev-parse", "HEAD"), ("rev-parse", "--verify", "HEAD^{tree}"), ("rev-parse", "--show-toplevel"), ("rev-parse", "--git-dir", "extra")):
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
        # `create` is a record verb, never an inspect verb: the read-only path stays read-only.
        grammar = self.launcher("inspect", "--target", str(self.target), "create", "no")
        self.assertNotEqual(grammar.returncode, 0)
        self.assertIn("accepts only --version, prime", grammar.stderr)
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
        self.assertIn("'--no-config' 'where' 'node@22.23.2'", windows)
        self.assertIn("finally", windows)
        self.assertIn("$childStatus = $LASTEXITCODE", windows)


@unittest.skipIf(NODE is None or os.name == "nt", "exact Node and POSIX fixture executables are required")
class SeedsRecordTests(LauncherFixture, unittest.TestCase):
    """The conductor-only queue-write seam: same receipt admission as inspect, plus
    compare-and-swap against the exact queue the conductor decided against and an exact
    post-write readback."""

    def setUp(self) -> None:
        super().setUp()
        self.queue = self.root / "queue target"
        self.queue.mkdir()
        self._run(["git", "init", "-q"], cwd=self.queue)
        self._run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.queue)
        self._run(["git", "config", "user.name", "Fixture"], cwd=self.queue)
        (self.queue / ".gitkeep").write_text("queue root\n", encoding="utf-8")
        self._run(["git", "add", ".gitkeep"], cwd=self.queue)
        self._run(["git", "commit", "-qm", "queue root"], cwd=self.queue)
        self.seeds = self.queue / ".seeds"
        self.seeds.mkdir()
        (self.seeds / "config.yaml").write_text("project: fixture\nversion: '1'\n", encoding="utf-8")
        (self.seeds / ".gitignore").write_text("*.lock\n", encoding="utf-8")
        self.issues = self.seeds / "issues.jsonl"
        self.plans = self.seeds / "plans.jsonl"
        self.write_records(self.issues, [])
        self.write_records(self.plans, [])
        self.assertEqual(self.bootstrap().returncode, 0)

    @staticmethod
    def canonical(record: dict[str, object]) -> str:
        """Serialize exactly as the queue writer's JSON.stringify does."""
        return json.dumps(record, separators=(",", ":"), ensure_ascii=False)

    def write_records(self, path: Path, records: list[dict[str, object]]) -> None:
        path.write_text("".join(f"{self.canonical(record)}\n" for record in records), encoding="utf-8")

    def read_records(self, path: Path) -> list[dict[str, object]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def digest(self, path: Path | None = None) -> str:
        return sha256((path or self.issues).read_bytes()).hexdigest()

    def seed(self, identifier: str, **overrides: object) -> dict[str, object]:
        record = {
            "id": identifier,
            "title": f"finding {identifier}",
            "status": "open",
            "type": "task",
            "priority": 2,
            "createdAt": "2026-08-01T00:00:00.000Z",
            "updatedAt": "2026-08-01T00:00:00.000Z",
        }
        record.update(overrides)
        return record

    def install_queue_writer(self, body: str) -> None:
        """Install a stand-in queue writer; `python3` receives the record argv after `--`."""
        python = shutil.which("python3")
        if not python:
            self.skipTest("python3 is required for the queue-writer fixture")
        script = self.root / "queue-writer.py"
        script.write_text(
            "import json, os, sys\n"
            "from pathlib import Path\n"
            f"issues = Path({str(self.issues)!r})\n"
            f"plans = Path({str(self.plans)!r})\n"
            "def canonical(record):\n"
            "    return json.dumps(record, separators=(',', ':'), ensure_ascii=False)\n"
            "def load(path):\n"
            "    return [json.loads(line) for line in path.read_text().splitlines() if line]\n"
            "def store(path, records):\n"
            "    path.write_text(''.join(canonical(record) + '\\n' for record in records))\n"
            # The launcher hands Bun its own flags, then the entry path, then the record argv.
            "argv = sys.argv[1:]\n"
            "argv = argv[next(i for i, value in enumerate(argv) if value.endswith('index.ts')) + 1:]\n"
            "argv = [value for value in argv if value != '--json']\n"
            + body,
            encoding="utf-8",
        )
        self._write_executable(
            self.queue_writer,
            f"#!/bin/sh\nexec {self._quote(python)} {self._quote(str(script))} \"$@\"\n",
        )

    def install_exact_queue_writer(self) -> None:
        """Model the real writer: create appends, update rewrites in place."""
        self.install_queue_writer(
            "verb = argv[0]\n"
            "flags = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
            "now = '2026-08-02T00:00:00.000Z'\n"
            "if verb == 'create':\n"
            "    records = load(issues)\n"
            "    record = {'id': 'fixture-0001', 'title': flags['--title'].strip(), 'status': 'open',\n"
            "              'type': flags.get('--type', 'task'), 'priority': int(flags.get('--priority', '2')),\n"
            "              'createdAt': now, 'updatedAt': now}\n"
            "    if '--description' in flags: record['description'] = flags['--description']\n"
            "    if '--labels' in flags:\n"
            "        labels = [label.strip().lower() for label in flags['--labels'].split(',') if label.strip()]\n"
            "        if labels: record['labels'] = labels\n"
            "    records.append(record)\n"
            "    store(issues, records)\n"
            "    print(json.dumps({'success': True, 'command': 'create', 'id': record['id']}))\n"
            "else:\n"
            "    identifier = argv[1]\n"
            "    flags = {argv[i]: argv[i + 1] for i in range(2, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
            "    records = load(issues)\n"
            "    index = next(i for i, record in enumerate(records) if record['id'] == identifier)\n"
            "    record = dict(records[index])\n"
            "    record['updatedAt'] = now\n"
            "    if '--status' in flags:\n"
            "        record['status'] = flags['--status']\n"
            "        if record['status'] != 'closed':\n"
            "            record.pop('closedAt', None); record.pop('closeReason', None)\n"
            "    if '--title' in flags: record['title'] = flags['--title'].strip()\n"
            "    if '--description' in flags: record['description'] = flags['--description']\n"
            "    if '--priority' in flags: record['priority'] = int(flags['--priority'])\n"
            "    labels = record.get('labels', [])\n"
            "    if '--set-labels' in flags:\n"
            "        labels = [label.strip().lower() for label in flags['--set-labels'].split(',') if label.strip()]\n"
            "    if '--add-label' in flags:\n"
            "        for label in flags['--add-label'].split(','):\n"
            "            if label.strip() and label.strip().lower() not in labels: labels.append(label.strip().lower())\n"
            "    if '--remove-label' in flags:\n"
            "        removed = {label.strip().lower() for label in flags['--remove-label'].split(',')}\n"
            "        labels = [label for label in labels if label not in removed]\n"
            "    if {'--set-labels', '--add-label', '--remove-label'} & set(flags):\n"
            "        record['labels'] = labels\n"
            "        if not labels: record.pop('labels', None)\n"
            "    records[index] = record\n"
            "    store(issues, records)\n"
            "    print(json.dumps({'success': True, 'command': 'update', 'issue': record}))\n"
        )

    def record(self, *args: str, writer: str = "conductor", expect: str | None = None) -> subprocess.CompletedProcess[str]:
        # Each invocation starts from a clean log so "never reached the queue writer" is exact.
        self.bun_log.unlink(missing_ok=True)
        return self.launcher(
            "record",
            "--target",
            str(self.queue),
            "--queue-writer",
            writer,
            "--expect-queue",
            expect if expect is not None else self.digest(),
            *args,
        )

    def install_exact_initializer(self) -> None:
        self.install_queue_writer(
            "target = Path.cwd()\n"
            "seeds = target / '.seeds'\n"
            "seeds.mkdir()\n"
            "(seeds / 'config.yaml').write_text(f'project: \"{target.name}\"\\nversion: \"1\"\\nmax_plan_depth: 3\\n')\n"
            "for name in ('issues.jsonl', 'templates.jsonl', 'plans.jsonl'):\n"
            "    (seeds / name).write_text('')\n"
            "(seeds / '.gitignore').write_text('*.lock\\n')\n"
            "attributes = target / '.gitattributes'\n"
            "existing = attributes.read_text() if attributes.exists() else ''\n"
            "lines = ['.seeds/issues.jsonl merge=union', '.seeds/templates.jsonl merge=union', '.seeds/plans.jsonl merge=union']\n"
            "existing_lines = set(existing.split('\\n'))\n"
            "missing = [line for line in lines if line not in existing_lines]\n"
            "if missing:\n"
            "    separator = '' if not existing or existing.endswith('\\n') else '\\n'\n"
            "    attributes.write_text(existing + separator + '\\n'.join(missing) + '\\n')\n"
            "print(json.dumps({'success': True, 'command': 'init', 'dir': str(seeds)}))\n"
        )

    def init(self, *, target: Path | None = None, writer: str = "conductor", expect: str = "absent", extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
        self.bun_log.unlink(missing_ok=True)
        return self.launcher(
            "record",
            "--target",
            str(target or self.queue),
            "--queue-writer",
            writer,
            "--expect-queue",
            expect,
            "init",
            *extra,
        )

    def test_lawful_init_creates_only_the_closed_surface_and_precise_gitattributes_append(self) -> None:
        shutil.rmtree(self.seeds)
        attributes = self.queue / ".gitattributes"
        attributes.write_text("*.generated linguist-generated\nlocal.dat merge=ours", encoding="utf-8")
        original = attributes.read_bytes()
        self.install_exact_initializer()

        result = self.init()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("recorded conductor queue initialization", result.stdout)
        self.assertEqual(
            {path.name for path in self.seeds.iterdir()},
            {".gitignore", "config.yaml", "issues.jsonl", "templates.jsonl", "plans.jsonl"},
        )
        self.assertEqual((self.seeds / ".gitignore").read_bytes(), b"*.lock\n")
        self.assertEqual(
            (self.seeds / "config.yaml").read_text(encoding="utf-8"),
            f'project: "{self.queue.name}"\nversion: "1"\nmax_plan_depth: 3\n',
        )
        for name in ("issues.jsonl", "templates.jsonl", "plans.jsonl"):
            self.assertEqual((self.seeds / name).read_bytes(), b"")
        self.assertEqual(
            attributes.read_bytes(),
            original
            + b"\n.seeds/issues.jsonl merge=union\n"
            + b".seeds/templates.jsonl merge=union\n"
            + b".seeds/plans.jsonl merge=union\n",
        )

    def test_init_requires_conductor_absent_shape_before_the_writer_starts(self) -> None:
        shutil.rmtree(self.seeds)
        self.install_exact_initializer()
        for name, kwargs in {
            "wrong writer": {"writer": "worker"},
            "digest expectation": {"expect": sha256(b"").hexdigest()},
            "extra argument": {"extra": ("--force",)},
        }.items():
            with self.subTest(request=name):
                refused = self.init(**kwargs)
                self.assertNotEqual(refused.returncode, 0)
                self.assertFalse(self.bun_log.exists())
                self.assertFalse(self.seeds.exists())

    def test_init_rejects_every_existing_or_redirected_seeds_surface(self) -> None:
        cases = {
            "empty directory": lambda: self.seeds.mkdir(),
            "partial directory": lambda: (self.seeds.mkdir(), (self.seeds / "issues.jsonl").write_text("")),
            "regular file": lambda: self.seeds.write_text("partial"),
            "symlink": lambda: os.symlink(self.root, self.seeds),
        }
        for name, mutation in cases.items():
            with self.subTest(surface=name):
                shutil.rmtree(self.seeds, ignore_errors=True)
                self.seeds.unlink(missing_ok=True)
                mutation()
                self.install_exact_initializer()
                refused = self.init()
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("absent .seeds", refused.stderr)
                self.assertFalse(self.bun_log.exists())

        shutil.rmtree(self.seeds, ignore_errors=True)
        self.seeds.unlink(missing_ok=True)
        shutil.rmtree(self.queue / ".git")
        (self.queue / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        refused = self.init()
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("linked worktree", refused.stderr)
        self.assertFalse(self.bun_log.exists())

    def test_init_requires_the_queue_owning_repository_root(self) -> None:
        shutil.rmtree(self.seeds)
        shutil.rmtree(self.queue / ".git")
        (self.queue / ".git").mkdir()
        self.install_exact_initializer()

        refused = self.init()

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("valid queue-owning Git repository root", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse(self.seeds.exists())

    def test_init_rejects_a_repository_subdirectory_with_a_spoofed_git_directory(self) -> None:
        shutil.rmtree(self.seeds)
        nested = self.queue / "nested"
        nested.mkdir()
        (nested / ".git").mkdir()
        self.install_exact_initializer()

        refused = self.init(target=nested)

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("not its queue-owning Git repository root", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse((nested / ".seeds").exists())

    def test_init_rejects_a_structural_git_spoof_without_an_exact_head_commit(self) -> None:
        shutil.rmtree(self.seeds)
        shutil.rmtree(self.queue / ".git")
        (self.queue / ".git" / "objects").mkdir(parents=True)
        (self.queue / ".git" / "refs" / "heads").mkdir(parents=True)
        (self.queue / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.install_exact_initializer()

        refused = self.init()

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("exact HEAD commit", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse(self.seeds.exists())

    def test_init_rejects_a_git_common_directory_redirect(self) -> None:
        shutil.rmtree(self.seeds)
        external = self.root / "external repository"
        self._run(["git", "clone", "-q", "--shared", str(self.queue), str(external)])
        redirected = self.root / "redirected queue root"
        redirected.mkdir()
        shutil.copytree(external / ".git", redirected / ".git")
        (redirected / ".git" / "commondir").write_text(
            str(self.queue / ".git") + "\n",
            encoding="utf-8",
        )
        self.install_exact_initializer()

        refused = self.init(target=redirected)

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("common Git directory redirects", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse((redirected / ".seeds").exists())

    def test_init_refuses_upstream_substring_matching_before_mutation(self) -> None:
        shutil.rmtree(self.seeds)
        attributes = self.queue / ".gitattributes"
        attributes.write_text(
            "# .seeds/issues.jsonl merge=union\n"
            ".seeds/templates.jsonl merge=union-extra\n",
            encoding="utf-8",
        )
        original = attributes.read_bytes()
        self.install_exact_initializer()

        refused = self.init()

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("substring-match", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse(self.seeds.exists())
        self.assertEqual(attributes.read_bytes(), original)

    def test_init_refuses_crlf_merge_rules_before_mutation(self) -> None:
        shutil.rmtree(self.seeds)
        attributes = self.queue / ".gitattributes"
        attributes.write_bytes(
            b".seeds/issues.jsonl merge=union\r\n"
            b".seeds/templates.jsonl merge=union\r\n"
            b".seeds/plans.jsonl merge=union\r\n"
        )
        original = attributes.read_bytes()
        self.install_exact_initializer()

        refused = self.init()

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("substring-match", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse(self.seeds.exists())
        self.assertEqual(attributes.read_bytes(), original)

    def test_init_refuses_non_utf8_gitattributes_before_mutation(self) -> None:
        shutil.rmtree(self.seeds)
        attributes = self.queue / ".gitattributes"
        attributes.write_bytes(b"binary-attribute=\xff\n")
        original = attributes.read_bytes()
        self.install_exact_initializer()

        refused = self.init()

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("non-UTF-8", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse(self.seeds.exists())
        self.assertEqual(attributes.read_bytes(), original)

    def test_init_rejects_non_regular_gitattributes_before_the_writer_starts(self) -> None:
        shutil.rmtree(self.seeds)
        for kind in ("directory", "symlink"):
            with self.subTest(kind=kind):
                attributes = self.queue / ".gitattributes"
                if attributes.is_symlink() or attributes.is_file():
                    attributes.unlink()
                elif attributes.is_dir():
                    attributes.rmdir()
                if kind == "directory":
                    attributes.mkdir()
                else:
                    elsewhere = self.root / "elsewhere-attributes"
                    elsewhere.write_text("foreign\n", encoding="utf-8")
                    os.symlink(elsewhere, attributes)
                self.install_exact_initializer()
                refused = self.init()
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("must be absent or a regular file", refused.stderr)
                self.assertFalse(self.bun_log.exists())

    def test_init_inherits_receipt_hash_and_environment_admissions(self) -> None:
        shutil.rmtree(self.seeds)
        self.install_exact_initializer()
        before = self.calls.read_text(encoding="utf-8")
        result = self.init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), before)
        contents = self.bun_log.read_text(encoding="utf-8")
        self.assertIn("init --json", contents)
        self.assertIn(f"PWD={self.queue}", contents)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", contents)
        for hostile in ("BUN_OPTIONS=", "NODE_OPTIONS=", "NPM_CONFIG_REGISTRY=", "MISE_DATA_DIR=", "SEEDS_DEBUG="):
            self.assertNotIn(hostile, contents)

        shutil.rmtree(self.seeds)
        entry = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli" / "src" / "index.ts"
        entry.write_text("drifted\n", encoding="utf-8")
        refused = self.init()
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("drift", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertFalse(self.seeds.exists())

    def test_init_reports_unknown_effect_for_failed_movement_and_clean_refusal_without_it(self) -> None:
        shutil.rmtree(self.seeds)
        self.install_queue_writer(
            "target = Path.cwd()\n"
            "(target / '.seeds').mkdir()\n"
            "(target / '.seeds' / 'partial').write_text('moved')\n"
            "sys.exit(7)\n"
        )
        unknown = self.init()
        self.assertNotEqual(unknown.returncode, 0)
        self.assertIn("effect is unknown", unknown.stderr)

        shutil.rmtree(self.seeds)
        attributes = self.queue / ".gitattributes"
        attributes.write_text("existing merge=ours\n", encoding="utf-8")
        original_attributes = attributes.read_bytes()
        self.install_queue_writer("sys.exit(7)\n")
        clean = self.init()
        self.assertNotEqual(clean.returncode, 0)
        self.assertIn("left .seeds and .gitattributes unchanged", clean.stderr)
        self.assertNotIn("effect is unknown", clean.stderr)
        self.assertFalse(self.seeds.exists())
        self.assertEqual(attributes.read_bytes(), original_attributes)

    def test_init_rejects_every_poststate_divergence(self) -> None:
        cases = {
            "extra file": "(seeds / 'smuggled').write_text('x')\n",
            "missing file": "(seeds / 'templates.jsonl').unlink()\n",
            "wrong config": "(seeds / 'config.yaml').write_text('project: smuggled\\nversion: \"1\"\\nmax_plan_depth: 3\\n')\n",
            "nonempty queue": "(seeds / 'issues.jsonl').write_text('{}\\n')\n",
            "wrong ignore": "(seeds / '.gitignore').write_text('*\\n')\n",
            "rewritten attributes": "attributes.write_text('rewritten\\n' + attributes.read_text())\n",
            "reported other dir": "reported = str(target / 'other')\n",
        }
        for name, mutation in cases.items():
            with self.subTest(divergence=name):
                shutil.rmtree(self.seeds, ignore_errors=True)
                (self.queue / ".gitattributes").unlink(missing_ok=True)
                self.install_queue_writer(
                    "target = Path.cwd()\n"
                    "seeds = target / '.seeds'\n"
                    "seeds.mkdir()\n"
                    "(seeds / 'config.yaml').write_text(f'project: \"{target.name}\"\\nversion: \"1\"\\nmax_plan_depth: 3\\n')\n"
                    "for filename in ('issues.jsonl', 'templates.jsonl', 'plans.jsonl'):\n"
                    "    (seeds / filename).write_text('')\n"
                    "(seeds / '.gitignore').write_text('*.lock\\n')\n"
                    "attributes = target / '.gitattributes'\n"
                    "attributes.write_text('.seeds/issues.jsonl merge=union\\n.seeds/templates.jsonl merge=union\\n.seeds/plans.jsonl merge=union\\n')\n"
                    "reported = str(seeds)\n"
                    + mutation
                    + "print(json.dumps({'success': True, 'command': 'init', 'dir': reported}))\n"
                )
                refused = self.init()
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("divergence", refused.stderr)

    def test_lawful_create_records_exactly_the_requested_fields(self) -> None:
        self.install_exact_queue_writer()
        existing = self.seed("fixture-0000")
        self.write_records(self.issues, [existing])
        before = self.digest()
        result = self.record(
            "create",
            "--title",
            "  gate excludes the secrets leaf  ",
            "--type",
            "bug",
            "--priority",
            "1",
            "--description",
            "Evidence: the check task omits it.",
            "--labels",
            " Class-Blocked-CI ,found-by-critic,",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("recorded conductor queue write: create fixture-0001", result.stdout)
        self.assertIn(f"queue sha256 {before} -> {self.digest()}", result.stdout)
        self.assertIn("authorizes no outward effect", result.stdout)
        records = self.read_records(self.issues)
        self.assertEqual(records[0], existing, "an unrelated record must survive byte-identically")
        self.assertEqual(
            records[1],
            {
                "id": "fixture-0001",
                "title": "gate excludes the secrets leaf",
                "status": "open",
                "type": "bug",
                "priority": 1,
                "createdAt": "2026-08-02T00:00:00.000Z",
                "updatedAt": "2026-08-02T00:00:00.000Z",
                "description": "Evidence: the check task omits it.",
                "labels": ["class-blocked-ci", "found-by-critic"],
            },
        )

    def test_lawful_update_records_exactly_the_requested_label_algebra(self) -> None:
        self.install_exact_queue_writer()
        untouched = self.seed("fixture-0000")
        target = self.seed("fixture-0001", labels=["stale", "keep"], closedAt="2026-08-01T00:00:00.000Z", closeReason="done")
        target["status"] = "closed"
        self.write_records(self.issues, [untouched, target])
        result = self.record(
            "update",
            "fixture-0001",
            "--status",
            "in_progress",
            "--set-labels",
            "base",
            "--add-label",
            "Wave-1,base",
            "--remove-label",
            "base",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        records = self.read_records(self.issues)
        self.assertEqual(records[0], untouched)
        self.assertEqual(records[1]["status"], "in_progress")
        self.assertEqual(records[1]["labels"], ["wave-1"])
        self.assertNotIn("closedAt", records[1], "reopening must drop stale close metadata")
        self.assertNotIn("closeReason", records[1])

    def test_record_requires_the_explicit_sole_queue_writer_acknowledgement(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [self.seed("fixture-0000")])
        pristine = self.issues.read_bytes()
        for argv in (
            ("record", "--target", str(self.queue), "create", "--title", "casual"),
            ("record", "--target", str(self.queue), "--expect-queue", self.digest(), "create", "--title", "casual"),
            ("record", "--target", str(self.queue), "--queue-writer", "conductor", "create", "--title", "casual"),
        ):
            with self.subTest(argv=argv):
                refused = self.launcher(*argv)
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("usage:", refused.stderr)
                self.assertEqual(self.issues.read_bytes(), pristine)
        for writer in ("worker", "reviewer", "critic", "integrator", "Conductor", ""):
            with self.subTest(writer=writer):
                refused = self.record("create", "--title", "casual", writer=writer)
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("admits only the sole queue writer", refused.stderr)
                self.assertEqual(self.issues.read_bytes(), pristine)

    def test_record_admits_only_create_and_update(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [self.seed("fixture-0000")])
        pristine = self.issues.read_bytes()
        for verb in ("delete", "prune", "close", "claim", "sync", "disposition", "archive", "ready", "prime", ""):
            with self.subTest(verb=verb):
                refused = self.record(verb, "fixture-0000")
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("only the conductor queue verbs create and update", refused.stderr)
                self.assertEqual(self.issues.read_bytes(), pristine)

    def test_record_refuses_compare_and_swap_drift(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [self.seed("fixture-0000")])
        stale = self.digest()
        # A concurrent writer lands between the conductor's decision and its queue write.
        self.write_records(self.issues, [self.seed("fixture-0000"), self.seed("fixture-0002")])
        current = self.issues.read_bytes()
        refused = self.record("create", "--title", "raced", expect=stale)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("compare-and-swap refused", refused.stderr)
        self.assertIn(stale, refused.stderr)
        self.assertIn(self.digest(), refused.stderr)
        self.assertEqual(self.issues.read_bytes(), current, "a refused compare-and-swap must not write")
        for expected in ("", "not-a-digest", "abc", stale.upper(), f"{stale}0"):
            with self.subTest(expected=expected):
                malformed = self.record("create", "--title", "raced", expect=expected)
                self.assertNotEqual(malformed.returncode, 0)
                self.assertIn("exact sha256", malformed.stderr)
                self.assertEqual(self.issues.read_bytes(), current)

    def test_record_refuses_readback_mismatch_against_the_requested_fields(self) -> None:
        divergences = {
            "wrong title": "record['title'] = 'a different finding'\n",
            "wrong type": "record['type'] = 'epic'\n",
            "wrong priority": "record['priority'] = 4\n",
            "dropped description": "record.pop('description', None)\n",
            "extra field": "record['assignee'] = 'somebody'\n",
            "wrong status": "record['status'] = 'closed'\n",
            "unrequested label": "record['labels'] = ['smuggled']\n",
            "split timestamps": "record['updatedAt'] = '2026-08-03T00:00:00.000Z'\n",
            "reported other id": "reported = 'fixture-9999'\n",
        }
        for name, divergence in divergences.items():
            with self.subTest(divergence=name):
                self.install_queue_writer(
                    "flags = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
                    "now = '2026-08-02T00:00:00.000Z'\n"
                    "record = {'id': 'fixture-0001', 'title': flags['--title'].strip(), 'status': 'open',\n"
                    "          'type': flags.get('--type', 'task'), 'priority': int(flags.get('--priority', '2')),\n"
                    "          'createdAt': now, 'updatedAt': now}\n"
                    "if '--description' in flags: record['description'] = flags['--description']\n"
                    "reported = record['id']\n"
                    + divergence
                    + "store(issues, load(issues) + [record])\n"
                    "print(json.dumps({'success': True, 'command': 'create', 'id': reported}))\n"
                )
                self.write_records(self.issues, [self.seed("fixture-0000")])
                refused = self.record("create", "--title", "a finding", "--description", "evidence")
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("queue readback divergence", refused.stderr)

    def test_record_refuses_a_writer_that_touches_records_outside_the_requested_delta(self) -> None:
        collateral = {
            "rewrote a neighbour": "records[0]['title'] = 'silently edited'\n",
            "dropped a neighbour": "del records[0]\n",
            "appended a second record": "records.append({**record, 'id': 'fixture-0002'})\n",
            "reordered the queue": "records.reverse()\n",
        }
        for name, mutation in collateral.items():
            with self.subTest(collateral=name):
                self.install_queue_writer(
                    "flags = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
                    "now = '2026-08-02T00:00:00.000Z'\n"
                    "record = {'id': 'fixture-0001', 'title': flags['--title'].strip(), 'status': 'open',\n"
                    "          'type': 'task', 'priority': 2, 'createdAt': now, 'updatedAt': now}\n"
                    "records = load(issues) + [record]\n"
                    + mutation
                    + "store(issues, records)\n"
                    "print(json.dumps({'success': True, 'command': 'create', 'id': record['id']}))\n"
                )
                self.write_records(self.issues, [self.seed("fixture-0000")])
                refused = self.record("create", "--title", "a finding")
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("divergence", refused.stderr)

    def test_record_bounds_the_plan_cascade_to_the_owning_plan(self) -> None:
        plan = {
            "id": "plan-0001",
            "title": "wave one",
            "status": "approved",
            "children": ["fixture-0001"],
            "createdAt": "2026-08-01T00:00:00.000Z",
            "updatedAt": "2026-08-01T00:00:00.000Z",
        }
        unrelated = {**plan, "id": "plan-0002", "children": ["fixture-9999"]}
        cascades = {
            "owning plan status and timestamp": ("plans[0].update(status='active', updatedAt=now)\n", 0),
            "plan that owns nothing here": ("plans[1].update(status='active', updatedAt=now)\n", 2),
            "plan children rewritten": ("plans[0].update(status='active', updatedAt=now, children=['fixture-0001', 'smuggled'])\n", 2),
            "plan title rewritten": ("plans[0].update(status='active', updatedAt=now, title='renamed')\n", 2),
            "plan invented": ("plans.append({**plans[0], 'id': 'plan-0003'})\n", 2),
            "plan status not a status": ("plans[0].update(status='smuggled', updatedAt=now)\n", 2),
        }
        for name, (mutation, expected_code) in cascades.items():
            with self.subTest(cascade=name):
                self.install_queue_writer(
                    "identifier = argv[1]\n"
                    "now = '2026-08-02T00:00:00.000Z'\n"
                    "flags = {argv[i]: argv[i + 1] for i in range(2, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
                    "records = load(issues)\n"
                    "index = next(i for i, record in enumerate(records) if record['id'] == identifier)\n"
                    "records[index] = {**records[index], 'status': flags['--status'], 'updatedAt': now}\n"
                    "store(issues, records)\n"
                    "plans_records = load(plans)\n"
                    + mutation.replace("plans[", "plans_records[").replace("plans.append", "plans_records.append")
                    + "store(plans, plans_records)\n"
                    "print(json.dumps({'success': True, 'command': 'update', 'issue': records[index]}))\n"
                )
                self.write_records(self.issues, [self.seed("fixture-0001")])
                self.write_records(self.plans, [plan, unrelated])
                result = self.record("update", "fixture-0001", "--status", "in_progress")
                self.assertEqual(result.returncode, expected_code, result.stderr or result.stdout)
                if expected_code:
                    self.assertIn("plan cascade", result.stderr)

    def test_record_refuses_a_plan_write_without_a_recorded_status_change(self) -> None:
        self.install_queue_writer(
            "identifier = argv[1]\n"
            "now = '2026-08-02T00:00:00.000Z'\n"
            "flags = {argv[i]: argv[i + 1] for i in range(2, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
            "records = load(issues)\n"
            "index = next(i for i, record in enumerate(records) if record['id'] == identifier)\n"
            "records[index] = {**records[index], 'title': flags['--title'], 'updatedAt': now}\n"
            "store(issues, records)\n"
            "store(plans, [{**load(plans)[0], 'status': 'active'}])\n"
            "print(json.dumps({'success': True, 'command': 'update', 'issue': records[index]}))\n"
        )
        self.write_records(self.issues, [self.seed("fixture-0001")])
        self.write_records(
            self.plans,
            [{"id": "plan-0001", "title": "wave one", "status": "approved", "children": ["fixture-0001"],
              "createdAt": "2026-08-01T00:00:00.000Z", "updatedAt": "2026-08-01T00:00:00.000Z"}],
        )
        refused = self.record("update", "fixture-0001", "--title", "renamed")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("without a recorded status change", refused.stderr)

    def test_record_refuses_a_writer_that_adds_or_removes_queue_files(self) -> None:
        for name, mutation in {
            "invented a queue file": "(issues.parent / 'smuggled.jsonl').write_text('{}\\n')\n",
            "removed a queue file": "(issues.parent / 'templates.jsonl').unlink()\n",
            "rewrote the config": "(issues.parent / 'config.yaml').write_text('project: hijacked\\n')\n",
        }.items():
            with self.subTest(surface=name):
                (self.seeds / "templates.jsonl").write_text("", encoding="utf-8")
                self.install_queue_writer(
                    "now = '2026-08-02T00:00:00.000Z'\n"
                    "flags = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
                    "record = {'id': 'fixture-0001', 'title': flags['--title'], 'status': 'open', 'type': 'task',\n"
                    "          'priority': 2, 'createdAt': now, 'updatedAt': now}\n"
                    "store(issues, load(issues) + [record])\n"
                    + mutation
                    + "print(json.dumps({'success': True, 'command': 'create', 'id': record['id']}))\n"
                )
                self.write_records(self.issues, [])
                refused = self.record("create", "--title", "a finding")
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("divergence", refused.stderr)

    def test_record_refuses_a_prestate_the_queue_writer_would_silently_rewrite(self) -> None:
        record = self.canonical(self.seed("fixture-0000"))
        for name, content in {
            "malformed line": f"{record}\n{{not json\n",
            "duplicate id": f"{record}\n{record}\n",
            "non-canonical serialization": json.dumps(self.seed("fixture-0000"), indent=None) + "\n",
            "missing trailing newline": record,
            "record without an id": '{"title":"anonymous"}\n',
        }.items():
            with self.subTest(prestate=name):
                self.install_exact_queue_writer()
                self.issues.write_text(content, encoding="utf-8")
                pristine = self.issues.read_bytes()
                refused = self.record("create", "--title", "a finding")
                self.assertNotEqual(refused.returncode, 0)
                self.assertFalse(self.bun_log.exists(), "the prestate is judged before the queue writer starts")
                self.assertEqual(self.issues.read_bytes(), pristine)

    def test_record_reports_an_unknown_effect_when_a_failed_writer_moved_the_queue(self) -> None:
        self.install_queue_writer(
            "store(issues, load(issues) + [{'id': 'fixture-0001', 'title': 'partial', 'status': 'open',\n"
            "  'type': 'task', 'priority': 2, 'createdAt': '2026-08-02T00:00:00.000Z',\n"
            "  'updatedAt': '2026-08-02T00:00:00.000Z'}])\n"
            "sys.exit(1)\n"
        )
        self.write_records(self.issues, [])
        refused = self.record("create", "--title", "a finding")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("effect is unknown", refused.stderr)

    def test_record_refuses_a_failed_writer_that_left_the_queue_intact(self) -> None:
        self.install_queue_writer("sys.exit(3)\n")
        self.write_records(self.issues, [self.seed("fixture-0000")])
        pristine = self.issues.read_bytes()
        refused = self.record("create", "--title", "a finding")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("the queue writer failed and left the queue", refused.stderr)
        self.assertEqual(self.issues.read_bytes(), pristine)

    def test_record_refuses_a_writer_that_does_not_report_the_exact_queue_write(self) -> None:
        for name, report in {
            "no json": "print('created something')\n",
            "not successful": "print(json.dumps({'success': False, 'command': 'create', 'id': 'fixture-0001'}))\n",
            "another command": "print(json.dumps({'success': True, 'command': 'close', 'id': 'fixture-0001'}))\n",
            "no id": "print(json.dumps({'success': True, 'command': 'create'}))\n",
        }.items():
            with self.subTest(report=name):
                self.install_queue_writer(
                    "now = '2026-08-02T00:00:00.000Z'\n"
                    "flags = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2) if argv[i].startswith('--')}\n"
                    "store(issues, load(issues) + [{'id': 'fixture-0001', 'title': flags['--title'],\n"
                    "  'status': 'open', 'type': 'task', 'priority': 2, 'createdAt': now, 'updatedAt': now}])\n"
                    + report
                )
                self.write_records(self.issues, [])
                refused = self.record("create", "--title", "a finding")
                self.assertNotEqual(refused.returncode, 0)

    def test_record_rejects_malformed_requests_before_the_queue_writer_starts(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [self.seed("fixture-0001")])
        pristine = self.issues.read_bytes()
        for name, args in {
            "create without a title": ("create", "--type", "bug"),
            "create with an empty title": ("create", "--title", "   "),
            "create with an unadmitted flag": ("create", "--title", "x", "--assignee", "somebody"),
            "create with a repeated flag": ("create", "--title", "x", "--title", "y"),
            "create with a valueless flag": ("create", "--title"),
            "create with a flag-shaped value": ("create", "--title", "--labels"),
            "create with an unknown type": ("create", "--title", "x", "--type", "chore"),
            "create with an out-of-range priority": ("create", "--title", "x", "--priority", "5"),
            "create with a P-shorthand priority": ("create", "--title", "x", "--priority", "P1"),
            "update without an id": ("update", "--status", "closed"),
            "update with no recorded field": ("update", "fixture-0001"),
            "update of an absent id": ("update", "fixture-9999", "--status", "closed"),
            "update with an unknown status": ("update", "fixture-0001", "--status", "archived"),
            "update with an unadmitted flag": ("update", "fixture-0001", "--clear-extensions", "yes"),
        }.items():
            with self.subTest(request=name):
                refused = self.record(*args)
                self.assertNotEqual(refused.returncode, 0)
                self.assertFalse(self.bun_log.exists(), f"{name} must be refused before the queue writer starts")
                self.assertEqual(self.issues.read_bytes(), pristine)

    def test_record_inherits_every_inspect_receipt_admission(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [])
        expected = self.digest()

        active = self.active_receipt_path()
        pristine_receipt = active.read_bytes()
        active.write_text(f'{{"schema":{RECEIPT_SCHEMA}}}\n', encoding="utf-8")
        partial = self.record("create", "--title", "a finding", expect=expected)
        self.assertNotEqual(partial.returncode, 0)
        self.assertIn("partial or invalid", partial.stderr)
        self.assertFalse(self.bun_log.exists())

        active.unlink()
        missing = self.record("create", "--title", "a finding", expect=expected)
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse(self.bun_log.exists())

        active.write_bytes(pristine_receipt)
        entry = self.seeds_root / "lib" / "node_modules" / "@os-eco" / "seeds-cli" / "src" / "index.ts"
        entry.write_text("drifted\n", encoding="utf-8")
        drift = self.record("create", "--title", "a finding", expect=expected)
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("drift", drift.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertEqual(self.read_records(self.issues), [])

    def test_record_runs_the_exact_bun_entry_with_the_inspect_environment_allowlist(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [])
        before = self.calls.read_text(encoding="utf-8")
        result = self.record("create", "--title", "a finding", "--type", "bug")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), before, "record must never invoke mise")
        contents = self.bun_log.read_text(encoding="utf-8")
        self.assertIn("--config=", contents)
        self.assertIn("--tsconfig-override=", contents)
        self.assertIn("--no-macros", contents)
        self.assertIn("--no-env-file --no-install", contents)
        self.assertIn("create --title a finding --type bug --json", contents)
        self.assertIn(f"PWD={self.queue}", contents)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", contents)
        for hostile in ("BUN_OPTIONS=", "BUN_INSPECT_PRELOAD=", "NODE_OPTIONS=", "NPM_CONFIG_REGISTRY=", "MISE_DATA_DIR=", "SEEDS_DEBUG="):
            self.assertNotIn(hostile, contents)

    def test_record_refuses_a_target_without_an_admissible_queue(self) -> None:
        self.install_exact_queue_writer()
        absent = self.record("create", "--title", "a finding", expect=self.digest())
        self.assertEqual(absent.returncode, 0, absent.stderr)

        for name, mutation in {
            "no seeds directory": lambda: shutil.rmtree(self.seeds),
            "no config": lambda: (self.seeds / "config.yaml").unlink(),
            "no queue file": lambda: self.issues.unlink(),
            "queue is a symlink": lambda: (self.issues.unlink(), os.symlink(self.root / "elsewhere.jsonl", self.issues)),
            "queue is a directory": lambda: (self.issues.unlink(), self.issues.mkdir()),
            "seeds directory is a symlink": lambda: (shutil.rmtree(self.seeds), os.symlink(self.root, self.seeds)),
        }.items():
            with self.subTest(target=name):
                self.tearDown()
                self.setUp()
                self.install_exact_queue_writer()
                (self.root / "elsewhere.jsonl").write_text("", encoding="utf-8")
                mutation()
                refused = self.record("create", "--title", "a finding", expect=sha256(b"").hexdigest())
                self.assertNotEqual(refused.returncode, 0)
                self.assertFalse(self.bun_log.exists())

    def test_record_refuses_a_linked_worktree_whose_queue_write_redirects(self) -> None:
        self.install_exact_queue_writer()
        shutil.rmtree(self.queue / ".git")
        (self.queue / ".git").write_text(f"gitdir: {self.root / 'main.git' / 'worktrees' / 'wt'}\n", encoding="utf-8")
        refused = self.record("create", "--title", "a finding")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("linked worktree", refused.stderr)
        self.assertFalse(self.bun_log.exists())
        self.assertEqual(self.read_records(self.issues), [])

    def test_record_ignores_the_queue_writers_own_lock_and_temporary_files(self) -> None:
        self.install_exact_queue_writer()
        self.write_records(self.issues, [])
        (self.seeds / "issues.jsonl.lock").write_text("", encoding="utf-8")
        (self.seeds / "issues.jsonl.lock.stale.abcd").write_text("", encoding="utf-8")
        (self.seeds / "issues.jsonl.tmp.abcd").write_text("", encoding="utf-8")
        result = self.record("create", "--title", "a finding")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.read_records(self.issues)), 1)


@unittest.skipUnless(os.name == "nt", "native Windows launcher fixture")
class NativeWindowsSeedsLauncherTests(unittest.TestCase):
    def test_real_locked_tuple_bootstraps_and_inspects_with_hostile_ambient_config(self) -> None:
        mise = shutil.which("mise.exe") or shutil.which("mise")
        git = shutil.which("git.exe") or shutil.which("git")
        self.assertIsNotNone(mise, "native Windows mise is required")
        self.assertIsNotNone(git, "native Windows Git is required")
        node_root = subprocess.run(
            [mise, "--no-config", "where", "node@22.23.2"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        bun_root = subprocess.run(
            [mise, "--no-config", "where", "bun@1.4.0"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        exact_node = Path(node_root) / "node.exe"
        exact_bun = Path(bun_root) / "bin" / "bun.exe"
        self.assertTrue(exact_node.is_file(), "exact Node 22.23.2 must be installed for the native fixture")
        self.assertTrue(exact_bun.is_file(), "exact Bun 1.4.0 must be installed for the native fixture")
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
            self.assertEqual(inspected.stdout.strip(), "0.5.15")
            receipt = json.loads(
                (state / "agentic-sdlc" / "seeds-runtime" / f"v{RECEIPT_SCHEMA}" / "active.json").read_text(encoding="utf-8")
            )
            self.assertTrue(os.path.samefile(receipt["tuple"]["git"]["path"], recorded_git))
            self.assertEqual(receipt["tuple"]["git"]["hash"], sha256(recorded_git.read_bytes()).hexdigest())
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
            self.assertEqual(direct_hostile.stdout, ".git\n")
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
            receipt_git_failure = subprocess.run(
                [
                    receipt["tuple"]["git"]["path"],
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "core.hooksPath=NUL",
                    "rev-parse",
                    "--git-dir",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                env=adapter_environment,
                check=False,
                timeout=60,
            )
            self.assertEqual(git_failure.returncode, receipt_git_failure.returncode)
            self.assertEqual(git_failure.stderr, receipt_git_failure.stderr)
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
