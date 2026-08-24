from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts import validate_bundle


ROOT = Path(__file__).parents[1]
VALIDATOR = Path("scripts/validate_bundle.py")
MIN_MISE_VERSION = "2026.4.27"
TOOLCHAIN_GATES_SKILL = ROOT / "skills" / "repo-toolchain-gates" / "SKILL.md"
LEFTHOOK = ROOT / "lefthook.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
SECRETS_CONFIG = ROOT / ".config" / "betterleaks.toml"
SECRETS_SCRIPT = ROOT / "scripts" / "secrets_scan.py"
SECRETS_RUN = "uv run --python 3.12.11 --script scripts/secrets_scan.py"
SECRETS_RUN_WINDOWS = "uv.exe run --python 3.12.11 --script scripts/secrets_scan.py"


def retype_directory_symlinks(root: Path) -> None:
    """Restore the source tree's symlink types after a copytree on Windows.

    `shutil.copytree(symlinks=True)` recreates every symlink without `target_is_directory`, so
    on Windows a copied directory link (the `plugin/*` entries) lands as a FILE-type link, and
    every later stat through it answers WinError 5 instead of a kind. POSIX symlinks carry no
    type, so this is a no-op everywhere else.
    """
    if os.name != "nt":
        return
    for directory, directories, filenames in os.walk(root):
        for name in (*directories, *filenames):
            link = Path(directory) / name
            if not link.is_symlink():
                continue
            target = os.readlink(str(link))
            if (Path(directory) / target).is_dir():
                link.unlink()
                link.symlink_to(target, target_is_directory=True)


class GateGraphTests(unittest.TestCase):
    # Toolchain drift is caught by the mise.toml <-> mise.lock cross-check plus the lock's own
    # byte pin, not by a Python restatement of `[tools]` (removed 2026-08-22, seed
    # agentic-sdlc-ab6a). The diagnostics below are therefore the derived ones. Two rows that the
    # old transcription carried are GONE ON PURPOSE and are recorded here rather than deleted
    # silently: `npm = "10.8.1"` (dropping the `depends = ["node"]` edge) and
    # `depends = []` on the Seeds pin now pass the validator. Both fail a fresh machine's first
    # `mise --locked install` loudly — a DevEx failure, not a trust boundary — and neither
    # changes which bytes get downloaded.
    TOOLCHAIN_MUTATIONS = (
        ("mise.toml", 'node = "22.23.2"', 'node = "22.23.1"', "mise.toml tool node requests"),
        ("mise.toml", 'bun = "1.4.0"', 'bun = "1.3.9"', "mise.toml tool bun requests"),
        # The renderer's npm identity is pinned separately from node, which bundles 10.9.8.
        # Drift here silently changes how the M0b node_modules tree is built.
        ("mise.toml", 'npm = { version = "10.8.1", depends = ["node"] }', 'npm = { version = "10.8.0", depends = ["node"] }', "mise.toml tool npm requests"),
        ("mise.toml", 'version = "0.5.15"', 'version = "0.5.14"', "mise.toml tool npm:@os-eco/seeds-cli requests"),
        ("mise.toml", 'package_manager = "npm"', 'package_manager = "bun"', "npm.package_manager must equal npm"),
        # Convenience-tier drift must fail exactly like bootstrap-tier drift. These tools are
        # not gate inputs, but an unpinned version is still an unreviewed binary.
        ("mise.toml", 'ripgrep = "15.2.0"', 'ripgrep = "14.1.1"', "mise.toml tool ripgrep requests"),
        ("mise.toml", 'fd = "10.4.2"', 'fd = "10.4.1"', "mise.toml tool fd requests"),
        ("mise.toml", 'jq = "1.8.2"', 'jq = "1.8.1"', "mise.toml tool jq requests"),
        ("mise.toml", 'gh = "2.98.0"', 'gh = "2.96.0"', "mise.toml tool gh requests"),
        ("mise.toml", 'version = "1.8.1"', 'version = "1.7.2"', "mise.toml tool github:betterleaks/betterleaks requests"),
        ("mise.toml", 'version = "2.28.0"', 'version = "2.10.2"', "mise.toml tool npm:@bitkyc08/opencodex requests"),
        # A tool dropped from the request is drift in the other direction: the lock would still
        # resolve a pin nothing asks for.
        ("mise.toml", 'gh = "2.98.0"\n', "", "mise.lock must resolve exactly the tools mise.toml requests"),
        # Re-adding the mermaid pin must fail. It was removed 2026-08-07 (docs/adr/0002
        # amendment): puppeteer's postinstall needs a zip archiver mise does not install, so
        # `mise --locked install` exited 1 on a slim image and took the other 12 tools with it.
        # The renderer never used this pin — it resolves mmdc from the repo's own node_modules.
        (
            "mise.toml",
            '[tools."npm:@bitkyc08/opencodex"]',
            '[tools."npm:@mermaid-js/mermaid-cli"]\nversion = "11.16.0"\ndepends = ["node"]\n\n[tools."npm:@bitkyc08/opencodex"]',
            "mise.toml tool npm:@mermaid-js/mermaid-cli is not resolved exactly once in mise.lock",
        ),
        # Any OTHER unreviewed npm pin is refused by name, not just the one that already bit us:
        # the npm backend runs arbitrary transitive install scripts, so each pin is screened.
        (
            "mise.toml",
            '[tools."npm:@bitkyc08/opencodex"]',
            '[tools."npm:some-unscreened-package"]\nversion = "1.0.0"\ndepends = ["node"]\n\n[tools."npm:@bitkyc08/opencodex"]',
            "npm-backend pins must be reviewed for install-script prerequisites",
        ),
        # The betterleaks backend must stay github: — ubi: is deprecated in mise 2027.1.0 and
        # locks version+backend only, losing per-platform checksums and attestation. Renaming the
        # key is what changes the backend, so the lock stops resolving the requested name.
        (
            "mise.toml",
            '[tools."github:betterleaks/betterleaks"]',
            '[tools."ubi:betterleaks/betterleaks"]',
            "mise.toml tool ubi:betterleaks/betterleaks is not resolved exactly once in mise.lock",
        ),
    )

    LOCKED_TOOLCHAIN = {
        "uv": {
            "version": "0.12.5",
            "backend": "aqua:astral-sh/uv",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "lefthook": {
            "version": "2.1.10",
            "backend": "aqua:evilmartians/lefthook",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "node": {
            "version": "22.23.2",
            "backend": "core:node",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "bun": {
            "version": "1.4.0",
            "backend": "core:bun",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "ripgrep": {
            "version": "15.2.0",
            "backend": "aqua:BurntSushi/ripgrep",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        # fd 10.4.2 publishes no x86_64-apple-darwin asset upstream, so mise locks 9 of the
        # 11 platform keys. Verified against the sharkdp/fd v10.4.2 release asset list.
        "fd": {
            "version": "10.4.2",
            "backend": "aqua:sharkdp/fd",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64",
                "windows-x64", "windows-x64-baseline",
            },
        },
        "jq": {
            "version": "1.8.2",
            "backend": "aqua:jqlang/jq",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "gh": {
            "version": "2.98.0",
            "backend": "aqua:cli/cli",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "github:betterleaks/betterleaks": {
            "version": "1.8.1",
            "backend": "github:betterleaks/betterleaks",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        # Bare `npm` resolves through the npm backend, so it locks version+backend only,
        # exactly like the scoped npm pins below.
        "npm": {"version": "10.8.1", "backend": "npm:npm"},
        "npm:@os-eco/seeds-cli": {"version": "0.5.15", "backend": "npm:@os-eco/seeds-cli"},
        "npm:@bitkyc08/opencodex": {
            "version": "2.28.0",
            "backend": "npm:@bitkyc08/opencodex",
        },
    }
    # Per-platform record shape differs by backend, so the expected field set is data, not a
    # special case buried in the assertion. aqua adds provenance only where the upstream
    # publishes attestations; github: records an API asset URL alongside the download URL.
    LOCK_PLATFORM_FIELDS = {
        "uv": {"checksum", "url", "provenance"},
        "lefthook": {"checksum", "url", "provenance"},
        "jq": {"checksum", "url", "provenance"},
        "gh": {"checksum", "url", "provenance"},
        "github:betterleaks/betterleaks": {"checksum", "url", "url_api"},
    }
    NPM_BACKED_LOCK_TOOLS = {
        "npm",
        "npm:@os-eco/seeds-cli",
        "npm:@bitkyc08/opencodex",
    }

    def test_repository_text_bytes_are_stable_across_host_checkouts(self) -> None:
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertIn("* text=auto eol=lf", attributes)

    # `contributor:setup`, the deprecated `setup` forwarder, and `mermaid:provision`'s exact
    # command are no longer transcribed (2026-08-22 shrink): they are convenience wiring, and a
    # wrong one is visible the first time an operator runs it. Their EXISTENCE is still required
    # through REQUIRED_TASKS, which the two `missing task` rows below exercise.
    MUTATIONS = (
        ("mise.toml", 'depends = ["validate", "test", "self-test", "secrets"]', 'depends = ["validate", "test"]', "check must contain only"),
        ("mise.toml", 'depends = ["validate", "test", "self-test", "secrets"]', 'depends = ["validate", "test", "self-test", "secrets"]\nrun = "python3 -c \'print(999)\'"', "check must contain only"),
        # Dropping the secrets leaf hollows the gate exactly like dropping self-test does.
        ("mise.toml", 'depends = ["validate", "test", "self-test", "secrets"]', 'depends = ["validate", "test", "self-test"]', "check must contain only"),
        # The secrets task must stay on the reviewed Git-visible wrapper: history scanning is a
        # separate consent-requiring pre-publish step, and a direct directory scan reaches ignored
        # operator runtime state instead of tracked + nonignored-untracked files.
        ("mise.toml", f'run = "{SECRETS_RUN}"', 'run = "betterleaks git . --config .config/betterleaks.toml"', "secrets must contain only"),
        ("mise.toml", f'run = "{SECRETS_RUN}"', 'run = "true"', "secrets must contain only"),
        ("mise.toml", f'run = "{SECRETS_RUN}"', 'run = "betterleaks dir . --config .config/betterleaks.toml"', "secrets must contain only"),
        ("mise.toml", f'run_windows = "{SECRETS_RUN_WINDOWS}"', 'run_windows = "betterleaks dir . --config .config/betterleaks.toml"', "secrets must contain only"),
        # The pinned config is the other half of the same control: pinning only the flag would
        # leave an edit to the file it points at free to disable the default ruleset.
        (".config/betterleaks.toml", "useDefault = true", "useDefault = false", ".config/betterleaks.toml must contain only [extend] useDefault = true"),
        # Renaming a Mermaid task away is caught: the renderer is advisory, but a task the
        # validator names must exist, or the M0b entry point is a dangling reference.
        ("mise.toml", '[tasks."mermaid:linux-test"]', '[tasks."mermaid:missing"]', "mise.toml missing task mermaid:linux-test"),
        ("mise.toml", '[tasks."mermaid:provision"]', '[tasks."mermaid:setup"]', "mise.toml missing task mermaid:provision"),
        # Provisioning downloads a pinned browser, so promoting it into the gate would make a
        # green verdict require network reachability. Wiring it into check must fail.
        (
            "mise.toml",
            'depends = ["validate", "test", "self-test", "secrets"]',
            'depends = ["validate", "test", "self-test", "secrets", "mermaid:linux-test"]',
            "check must contain only",
        ),
        ("mise.toml", 'run = "uv run --python 3.12.11 --script scripts/validate_bundle.py"', 'run = "python3 scripts/validate_bundle.py"', "task validate.run must equal"),
        # Every leaf `check` depends on is pinned by exact command, because hollowing any one of
        # them to `true` leaves a green gate that ran nothing.
        ("mise.toml", 'run = "uv run --python 3.12.11 --with pyyaml==6.0.3 python -m unittest discover -s tests"', 'run = "true"', "task test.run must equal"),
        ("mise.toml", 'run = "uv run --python 3.12.11 --script scripts/install_skill_bundle.py self-test"', 'run = "true"', "task self-test.run must equal"),
        ("mise.toml", "locked = true", "locked = false", "must enable locked tool resolution"),
        ("mise.toml", 'min_version = "2026.4.27"', 'min_version = "2025.1.0"', "must require mise 2026.4.27"),
        ("scripts/validate-bundle.sh", 'exec mise -C "$root" exec -- uv run --python 3.12.11', "exec python3", "exec-only pinned mise/uv wrapper"),
        ("scripts/bump-version.sh", 'mise -C "$repo_root" exec -- uv run --python 3.12.11 python - "$manifest"', '# mise -C "$repo_root" exec -- uv run --python 3.12.11 python -\npython3 - "$manifest"', "bump-version.sh must use only"),
        ("scripts/bump-version.sh", "\nPY\n", "\nPY\npython3 -c 'print(1)'\n", "must end at the pinned Python heredoc"),
        ("lefthook.yml", "run: mise run self-test", "run: mise run check", "documented best-effort gate subsets"),
        # Unwiring the pre-push secrets scan is caught; a hook subset is only honest if the
        # documented bytes and the file agree.
        ("lefthook.yml", "    secrets:\n      run: mise run secrets\n", "", "documented best-effort gate subsets"),
        # pre-commit stays fast: the secrets scan belongs to pre-push, not pre-commit.
        ("lefthook.yml", "    validate:\n      run: mise run validate\n", "    validate:\n      run: mise run validate\n    secrets:\n      run: mise run secrets\n", "documented best-effort gate subsets"),
        (".github/workflows/validate.yml", "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5", "actions/checkout@v4", "CI workflow must equal the single authoritative mise run check graph"),
        (".github/workflows/validate.yml", "jdx/mise-action@c37c93293d6b742fc901e1406b8f764f6fb19dac", "jdx/mise-action@v2", "CI workflow must equal the single authoritative mise run check graph"),
        (".github/workflows/validate.yml", "run: mise run check", "run: mise run validate", "CI workflow must equal the single authoritative mise run check graph"),
        (".github/workflows/validate.yml", "        run: mise run check", "        run: mise run check\n      - name: Bypass\n        run: curl https://example.com", "CI workflow must equal the single authoritative mise run check graph"),
        (".github/workflows/validate.yml", "        run: mise run check", "        run: mise run check\n      - name: Bypass\n        run : curl https://example.com", "CI workflow must equal the single authoritative mise run check graph"),
    )

    def copied_repo(self, temp: str) -> Path:
        repo = Path(temp) / "repo"
        # Provisioned trees are excluded so a mutation fixture costs the same on a host that
        # has run Mermaid provisioning as on one that never has.
        shutil.copytree(
            ROOT,
            repo,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git", "node_modules", ".mermaid-runtime", "__pycache__"),
        )
        retype_directory_symlinks(repo)
        return repo

    def run_validator(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(repo / VALIDATOR), "--root", str(repo)],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )

    def isolated_mise_env(self, temp: str, *, unlock: bool = False) -> dict[str, str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("MISE_") and key != "CI"
        }
        env |= {
            "HOME": str(Path(temp) / "home"),
            "MISE_DATA_DIR": str(Path(temp) / "mise-data"),
            "MISE_STATE_DIR": str(Path(temp) / "mise-state"),
            "MISE_CACHE_DIR": str(Path(temp) / "mise-cache"),
            "MISE_CONFIG_DIR": str(Path(temp) / "mise-config"),
        }
        if unlock:
            env["MISE_LOCKED"] = "0"
        return env

    def assert_lock_mutation_fails(self, old: bytes, new: bytes) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy2(ROOT / "mise.toml", root / "mise.toml")
            before = (ROOT / "mise.lock").read_bytes()
            self.assertIn(old, before)
            (root / "mise.lock").write_bytes(before.replace(old, new, 1))
            result = validate_bundle.Validation()
            validate_bundle.validate_mise(root, result)
        self.assertIn("mise.lock SHA-256 must equal the canonical generated lock", result.errors)

    def test_unexpected_lock_root_table_fails(self) -> None:
        self.assert_lock_mutation_fails(
            b"\n[[tools.uv]]",
            b'\n[unexpected]\nvalue = "not generated"\n\n[[tools.uv]]',
        )

    def test_unexpected_non_seeds_tool_entry_field_fails(self) -> None:
        self.assert_lock_mutation_fails(
            b'[[tools.node]]\nversion = "22.23.2"',
            b'[[tools.node]]\nversion = "22.23.2"\nunexpected = "not generated"',
        )

    def test_current_gate_graph_is_valid(self) -> None:
        result = self.run_validator(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipIf(
        os.name == "nt" or os.geteuid() == 0,
        "the unstatable-path fixture needs POSIX permission semantics and a non-root euid",
    )
    def test_an_unstatable_path_does_not_crash_the_validator(self) -> None:
        """An entry the walk can list but not stat must be skipped like an unreadable one.

        Windows CI produced this shape organically (a file-typed symlink to a directory answers
        WinError 5 on stat); a read-permission-only directory produces the same EACCES-on-stat on
        POSIX, so the guard has a positive control on every platform the suite runs on.
        """
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            trap = repo / "operator-notes"
            trap.mkdir()
            (trap / "unstatable.bin").write_bytes(b"kind unknown\n")
            trap.chmod(0o400)
            try:
                result = self.run_validator(repo)
            finally:
                trap.chmod(0o700)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_toolchain_config_mutations_fail(self) -> None:
        executed = 0
        for relative_path, old, new, diagnostic in self.TOOLCHAIN_MUTATIONS:
            with self.subTest(old=old), tempfile.TemporaryDirectory() as temp:
                repo = self.copied_repo(temp)
                path = repo / relative_path
                text = path.read_text(encoding="utf-8")
                self.assertIn(old, text)
                path.write_text(text.replace(old, new, 1), encoding="utf-8")
                result = self.run_validator(repo)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(diagnostic, result.stderr)
                executed += 1
        self.assertEqual(executed, len(self.TOOLCHAIN_MUTATIONS))

    def test_generated_toolchain_lock_records_are_complete(self) -> None:
        lock = tomllib.loads((ROOT / "mise.lock").read_text(encoding="utf-8"))["tools"]
        for name, expected in self.LOCKED_TOOLCHAIN.items():
            with self.subTest(tool=name):
                entries = lock.get(name, [])
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0].get("version"), expected["version"])
                self.assertEqual(entries[0].get("backend"), expected["backend"])
                platform_keys = {key for key in entries[0] if key.startswith("platforms.")}
                if name in self.NPM_BACKED_LOCK_TOOLS:
                    self.assertEqual(set(entries[0]), {"version", "backend"})
                else:
                    expected_platforms = expected["platforms"]
                    self.assertEqual(platform_keys, {f"platforms.{platform}" for platform in expected_platforms})
                    expected_fields = self.LOCK_PLATFORM_FIELDS.get(name, {"checksum", "url"})
                    for key in platform_keys:
                        self.assertEqual(set(entries[0][key]), expected_fields)

    def test_generated_toolchain_lock_has_exact_tool_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            path = repo / "mise.lock"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text + '\n[[tools.python]]\nversion = "3.12.11"\nbackend = "core:python"\n',
                encoding="utf-8",
            )
            result = self.run_validator(repo)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("mise.lock must resolve exactly the tools mise.toml requests", result.stderr)

    @unittest.skipUnless(shutil.which("mise"), "mise is required for install lock behavior")
    def test_runtime_install_preserves_reviewed_lock_bytes_and_validity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            lock_path = repo / "mise.lock"
            before = lock_path.read_bytes()
            env = self.isolated_mise_env(temp)
            installed = subprocess.run(
                ["mise", "-C", str(repo), "install", "--yes"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            self.assertEqual(lock_path.read_bytes(), before)
            result = self.run_validator(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("mise"), "mise is required for generated lock behavior")
    def test_canonical_lock_regeneration_is_byte_identical_and_valid(self) -> None:
        version = subprocess.run(
            ["mise", "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(version.returncode, 0, version.stdout + version.stderr)
        actual_version = version.stdout.split()[0]
        if actual_version != MIN_MISE_VERSION:
            self.skipTest(
                "canonical lock regeneration requires exact maintenance mise "
                f"{MIN_MISE_VERSION}; found {actual_version}"
            )
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            lock_path = repo / "mise.lock"
            before = lock_path.read_bytes()
            env = self.isolated_mise_env(temp, unlock=True)
            generated = subprocess.run(
                ["mise", "-C", str(repo), "lock", "--yes"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            self.assertEqual(lock_path.read_bytes(), before)
            result = self.run_validator(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_toolchain_lock_mutations_fail(self) -> None:
        mutations = (
            (b'[[tools.node]]\nversion = "22.23.2"', b'[[tools.node]]\nversion = "22.23.1"'),
            (b'[[tools.bun]]\nversion = "1.4.0"', b'[[tools.bun]]\nversion = "1.3.9"'),
            (
                b'[[tools."npm:@os-eco/seeds-cli"]]\nversion = "0.5.15"',
                b'[[tools."npm:@os-eco/seeds-cli"]]\nversion = "0.5.14"',
            ),
            (
                b'backend = "npm:@os-eco/seeds-cli"',
                b'backend = "npm:@os-eco/seeds-cli"\ntransitive_integrity = "unsupported"',
            ),
            (b'[tools.node."platforms.linux-x64"]\nchecksum = ', b'[tools.node."platforms.linux-x64"]\nchecksum = "sha256:' + b"0" * 64 + b'" # '),
            (b'[tools.bun."platforms.linux-x64"]\nchecksum = ', b'[tools.bun."platforms.linux-x64"]\nchecksum = "sha256:' + b"0" * 64 + b'" # '),
        )
        for old, new in mutations:
            with self.subTest(mutation=old[:40]):
                self.assert_lock_mutation_fails(old, new)

    def test_lock_mutation_fails_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            path = repo / "mise.lock"
            path.write_bytes(path.read_bytes().replace(b'backend = "core:node"', b'backend = "core:tampered"', 1))
            result = self.run_validator(repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("mise.lock SHA-256 must equal the canonical generated lock", result.stderr)

    def test_all_hollowing_mutations_fail(self) -> None:
        executed = 0
        for relative_path, old, new, diagnostic in self.MUTATIONS:
            with self.subTest(path=relative_path, diagnostic=diagnostic), tempfile.TemporaryDirectory() as temp:
                repo = self.copied_repo(temp)
                path = repo / relative_path
                text = path.read_text(encoding="utf-8")
                self.assertIn(old, text)
                path.write_text(text.replace(old, new, 1), encoding="utf-8")
                self.assertNotEqual(path.read_text(encoding="utf-8"), text)
                result = self.run_validator(repo)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(diagnostic, result.stderr)
                executed += 1
        self.assertEqual(executed, len(self.MUTATIONS))

    def test_folded_description_variants_cannot_bypass_validation(self) -> None:
        variants = (
            ("description: |\nextra:\n  not-a-description", "missing description"),
            ("description: >2\n  " + "x" * 1025, "description exceeds 1024"),
            ("description: |\n  short\n\n  " + "x" * 1025, "description exceeds 1024"),
            # A plain (unquoted, non-block) multiline scalar carries its bulk on continuation
            # lines; a first-line-only measure reads it as 28 characters (agentic-sdlc-e78f).
            ("description: plain first line stays short\n  " + "x" * 1025, "description exceeds 1024"),
        )
        executed = 0
        for replacement, diagnostic in variants:
            with self.subTest(replacement=replacement[:16]), tempfile.TemporaryDirectory() as temp:
                repo = self.copied_repo(temp)
                skill = repo / "skills" / "stacked-prs" / "SKILL.md"
                text = skill.read_text(encoding="utf-8")
                original = next(line for line in text.splitlines() if line.startswith("description:"))
                skill.write_text(text.replace(original, replacement, 1), encoding="utf-8")
                result = self.run_validator(repo)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(f"stacked-prs: {diagnostic}", result.stderr)
                executed += 1
        self.assertEqual(executed, len(variants))

    def test_block_scalar_description_at_cap_boundary(self) -> None:
        # Positive control for the multiline variants above: the cap must measure the parsed
        # value, not refuse every multiline description. The whole description block is
        # replaced — splicing only the first line would fold the fixture's own continuation
        # lines into the planted scalar and push an exact-boundary value over the cap.
        for length, returncode, diagnostic in ((1024, 0, None), (1025, 1, "description exceeds 1024")):
            with self.subTest(length=length), tempfile.TemporaryDirectory() as temp:
                repo = self.copied_repo(temp)
                skill = repo / "skills" / "stacked-prs" / "SKILL.md"
                lines = skill.read_text(encoding="utf-8").splitlines()
                start = next(index for index, line in enumerate(lines) if line.startswith("description:"))
                end = next(index for index in range(start + 1, len(lines)) if not lines[index].startswith(" "))
                planted = lines[:start] + ["description: >-", "  " + "x" * length] + lines[end:]
                skill.write_text("\n".join(planted) + "\n", encoding="utf-8")
                result = self.run_validator(repo)
                self.assertEqual(result.returncode, returncode, result.stdout + result.stderr)
                if diagnostic:
                    self.assertIn(f"stacked-prs: {diagnostic}", result.stderr)

    @unittest.skipUnless(shutil.which("mise"), "mise is required for trust behavior")
    def test_paranoid_mode_requires_per_path_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            home = Path(temp) / "home"
            home.mkdir()
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("MISE_") and key != "CI"
            }
            env |= {
                "HOME": str(home),
                "MISE_PARANOID": "1",
                "MISE_DATA_DIR": str(Path(temp) / "mise-data"),
                "MISE_STATE_DIR": str(Path(temp) / "mise-state"),
                "MISE_CACHE_DIR": str(Path(temp) / "mise-cache"),
                "MISE_CONFIG_DIR": str(Path(temp) / "mise-config"),
            }
            before = subprocess.run(["mise", "-C", str(repo), "tasks"], env=env, text=True, capture_output=True, check=False)
            self.assertNotEqual(before.returncode, 0)
            self.assertIn("not trusted", before.stderr)

            trusted = subprocess.run(["mise", "trust", str(repo / "mise.toml")], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(trusted.returncode, 0, trusted.stderr)
            after = subprocess.run(["mise", "-C", str(repo), "tasks"], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(after.returncode, 0, after.stderr)

    # --- G2/G4: betterleaks doctrine-vs-wiring reconciliation (spec §G2.3, §G4) ---

    def test_betterleaks_is_pinned_locked_and_wired(self) -> None:
        """The scanner is pinned, locked, AND reachable from the authoritative gate.

        History: this tree pinned betterleaks in [tools] (Option A, 2026-08-05) while leaving
        the invocation unwired, and the skill disclosed that honestly. As of 2026-08-06 the
        gate is wired: `[tasks.secrets]` runs the working-tree scan and `[tasks.check]` depends
        on it, so `mise run check` (and therefore CI) screens the tree. This test now asserts
        the wiring exists rather than tracking a disclosure, and it still asserts the two facts
        that keep the wiring meaningful: the pin is locked per platform, and the wired verb is
        the working-tree scan, not the consent-requiring history scan.
        """
        skill = TOOLCHAIN_GATES_SKILL.read_text(encoding="utf-8")
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        mise = (ROOT / "mise.toml").read_text(encoding="utf-8")
        lefthook = LEFTHOOK.read_text(encoding="utf-8")

        pinned = re.search(
            r"(?m)^(?:betterleaks|gitleaks)\s*=|\[tools\.\"[^\"]*(?:betterleaks|gitleaks)[^\"]*\"\]",
            mise,
        )
        self.assertTrue(pinned, "the wired secrets scanner must be pinned in [tools]")

        # A pinned scanner must be locked, not merely named, or "same version everywhere" is a
        # claim with nothing behind it.
        lock = tomllib.loads((ROOT / "mise.lock").read_text(encoding="utf-8"))["tools"]
        scanner_keys = [k for k in lock if "betterleaks" in k or "gitleaks" in k]
        self.assertEqual(
            len(scanner_keys), 1, "a pinned secrets scanner must appear exactly once in mise.lock"
        )
        entry = lock[scanner_keys[0]][0]
        platform_keys = [k for k in entry if k.startswith("platforms.")]
        self.assertTrue(platform_keys, "a pinned secrets scanner must lock per-platform records")
        for key in platform_keys:
            self.assertIn("checksum", entry[key])
        # ubi: is deprecated for removal in mise 2027.1.0 and locks no per-platform checksum.
        self.assertNotIn("ubi:", scanner_keys[0])

        # The gate is wired through the Git-visible wrapper. The wrapper owns exact path
        # selection and passes the pinned config on every scanner batch.
        secrets = config["tasks"]["secrets"]
        self.assertEqual(secrets["run"], SECRETS_RUN)
        self.assertEqual(secrets["run_windows"], SECRETS_RUN_WINDOWS)
        self.assertTrue(SECRETS_SCRIPT.is_file())
        wrapper = SECRETS_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ls-files", wrapper)
        self.assertIn("--exclude-standard", wrapper)
        self.assertIn('"--config"', wrapper)
        self.assertIn('"--redact=100"', wrapper)
        self.assertEqual(
            tomllib.loads(SECRETS_CONFIG.read_text(encoding="utf-8")),
            {"extend": {"useDefault": True}},
        )
        self.assertIn("secrets", config["tasks"]["check"]["depends"])
        # pre-push carries the scan; pre-commit stays fast.
        self.assertIn("mise run secrets", lefthook.split("pre-push:", 1)[1])
        self.assertNotIn("secrets", lefthook.split("pre-push:", 1)[0])
        # History scanning stays out of every automatic gate: it needs explicit consent. Only
        # executed strings are checked -- prose explaining the exclusion is not an invocation.
        history_verb = re.compile(r"(?:betterleaks|gitleaks)\s+git\b")
        for name, task in config["tasks"].items():
            for field in ("run", "run_windows"):
                command = task.get(field) if isinstance(task, dict) else None
                if isinstance(command, str):
                    with self.subTest(task=name, field=field):
                        self.assertNotRegex(command, history_verb)
        for run_line in re.findall(
            r"(?m)^\s*run:\s*(.+)$", CI_WORKFLOW.read_text(encoding="utf-8") + "\n" + lefthook
        ):
            self.assertNotRegex(run_line, history_verb)

        # The skill must now describe a wired gate, must not still call the invocation
        # advisory/opt-in/unwired, and must not turn a clean scan into authorization.
        self.assertRegex(skill, r"(?i)betterleaks[^.\n]{0,120}(?:is wired|runs on every|`?mise run check`?)")
        self.assertNotRegex(skill, r"(?i)invocation (?:advisory|opt-in|not wired)")
        self.assertRegex(skill, r"(?i)evidence, not authorization|authorizes nothing|is not authorization")

    def test_check_depends_are_the_wired_gate_leaves(self) -> None:
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        depends = config["tasks"]["check"]["depends"]
        self.assertEqual(depends, ["validate", "test", "self-test", "secrets"])
        # Every declared leaf must be a real task; a phantom dependency is not a gate.
        for leaf in depends:
            self.assertIn(leaf, config["tasks"])

    def test_mermaid_rendering_is_advisory_and_not_a_gate_leaf(self) -> None:
        """`mise run check` must stay green on a host that has never provisioned the renderer.

        Provisioning downloads a pinned browser, so any Mermaid leaf in the gate would make a
        green verdict depend on network reachability and on ~200 MB of unreviewed runtime.
        """
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        tasks = config["tasks"]
        for name in ("mermaid:provision", "mermaid:linux-test"):
            self.assertIn(name, tasks)
        self.assertNotIn("mermaid:provision", config["tasks"]["check"]["depends"])
        self.assertNotIn("mermaid:linux-test", config["tasks"]["check"]["depends"])
        # No gate leaf may reach a Mermaid task transitively either.
        for leaf in config["tasks"]["check"]["depends"]:
            self.assertEqual([], [name for name in tasks[leaf].get("depends", []) if name.startswith("mermaid:")])
        # The renderer's own suite lives outside `tests`, so `mise run test` cannot pull in a
        # provisioning requirement through unittest discovery.
        self.assertIn("discover -s tests_linux", tasks["mermaid:linux-test"]["run"])
        self.assertIn("discover -s tests", tasks["test"]["run"])
        lefthook = (ROOT / "lefthook.yml").read_text(encoding="utf-8")
        self.assertNotIn("mermaid", lefthook)
        self.assertNotIn("mermaid", CI_WORKFLOW.read_text(encoding="utf-8"))

    def test_removing_secrets_from_check_is_caught(self) -> None:
        """Mutation negative: the wiring cannot be dropped while the validator stays green."""
        with tempfile.TemporaryDirectory() as temp:
            repo = self.copied_repo(temp)
            path = repo / "mise.toml"
            text = path.read_text(encoding="utf-8")
            hollowed = text.replace(
                'depends = ["validate", "test", "self-test", "secrets"]',
                'depends = ["validate", "test", "self-test"]',
                1,
            )
            self.assertNotEqual(hollowed, text)
            path.write_text(hollowed, encoding="utf-8")
            result = self.run_validator(repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("check must contain only", result.stderr)

    def test_no_second_task_runner(self) -> None:
        mise = (ROOT / "mise.toml").read_text(encoding="utf-8")
        lefthook = LEFTHOOK.read_text(encoding="utf-8")
        ci = CI_WORKFLOW.read_text(encoding="utf-8")
        # No competing task-runner entrypoint drives gates.
        forbidden = (
            re.compile(r"(?m)^\s*run:\s*(?:make|just|task)\s"),
            re.compile(r"(?m)^\s*run:\s*npm run\s"),
            re.compile(r"\bmakefile\b", re.I),
            re.compile(r"\bjustfile\b", re.I),
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern.pattern):
                self.assertNotRegex(lefthook, pattern)
                self.assertNotRegex(ci, pattern)
        # CI and hooks drive gates only through `mise run ...`.
        for run_line in re.findall(r"(?m)^\s*run:\s*(.+)$", ci + "\n" + lefthook):
            stripped = run_line.strip()
            if stripped.startswith("mise "):
                continue
            self.fail(f"non-mise gate entrypoint: {stripped!r}")
        # mise.toml declares no alternate package manager beyond the pinned npm.
        self.assertNotRegex(mise, r'(?m)package_manager\s*=\s*"(?:bun|pnpm|yarn)"')


if __name__ == "__main__":
    unittest.main()
