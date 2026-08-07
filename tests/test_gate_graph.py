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


class GateGraphTests(unittest.TestCase):
    TOOLCHAIN_MUTATIONS = (
        ("mise.toml", 'node = "22.22.3"', 'node = "22.22.2"', "mise.toml tools must equal"),
        ("mise.toml", 'bun = "1.3.10"', 'bun = "1.3.9"', "mise.toml tools must equal"),
        ("mise.toml", 'version = "0.5.14"', 'version = "0.5.13"', "mise.toml tools must equal"),
        ("mise.toml", 'package_manager = "npm"', 'package_manager = "bun"', "npm.package_manager must equal npm"),
        ("mise.toml", 'depends = ["node"]', 'depends = []', "Seeds tool must depend on node"),
        # Convenience-tier drift must fail exactly like bootstrap-tier drift. These tools are
        # not gate inputs, but an unpinned version is still an unreviewed binary.
        ("mise.toml", 'ripgrep = "15.2.0"', 'ripgrep = "14.1.1"', "mise.toml tools must equal"),
        ("mise.toml", 'fd = "10.4.2"', 'fd = "10.4.1"', "mise.toml tools must equal"),
        ("mise.toml", 'jq = "1.8.2"', 'jq = "1.8.1"', "mise.toml tools must equal"),
        ("mise.toml", 'gh = "2.97.0"', 'gh = "2.96.0"', "mise.toml tools must equal"),
        ("mise.toml", 'version = "1.7.3"', 'version = "1.7.2"', "mise.toml tools must equal"),
        ("mise.toml", 'version = "11.16.0"', 'version = "11.15.0"', "mise.toml tools must equal"),
        ("mise.toml", 'version = "2.10.2"', 'version = "2.10.1"', "mise.toml tools must equal"),
        # The betterleaks backend must stay github: — ubi: is deprecated in mise 2027.1.0 and
        # locks version+backend only, losing per-platform checksums and attestation.
        (
            "mise.toml",
            '[tools."github:betterleaks/betterleaks"]',
            '[tools."ubi:betterleaks/betterleaks"]',
            "mise.toml tools must equal",
        ),
    )

    LOCKED_TOOLCHAIN = {
        "uv": {
            "version": "0.11.17",
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
            "version": "22.22.3",
            "backend": "core:node",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "bun": {
            "version": "1.3.10",
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
            "version": "2.97.0",
            "backend": "aqua:cli/cli",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "github:betterleaks/betterleaks": {
            "version": "1.7.3",
            "backend": "github:betterleaks/betterleaks",
            "platforms": {
                "linux-arm64", "linux-arm64-musl", "linux-x64", "linux-x64-baseline",
                "linux-x64-musl", "linux-x64-musl-baseline", "macos-arm64", "macos-x64",
                "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
            },
        },
        "npm:@os-eco/seeds-cli": {"version": "0.5.14", "backend": "npm:@os-eco/seeds-cli"},
        "npm:@mermaid-js/mermaid-cli": {
            "version": "11.16.0",
            "backend": "npm:@mermaid-js/mermaid-cli",
        },
        "npm:@bitkyc08/opencodex": {
            "version": "2.10.2",
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
        "npm:@os-eco/seeds-cli",
        "npm:@mermaid-js/mermaid-cli",
        "npm:@bitkyc08/opencodex",
    }

    MUTATIONS = (
        ("mise.toml", 'depends = ["validate", "test", "self-test", "secrets"]', 'depends = ["validate", "test"]', "check must contain only"),
        ("mise.toml", 'depends = ["validate", "test", "self-test", "secrets"]', 'depends = ["validate", "test", "self-test", "secrets"]\nrun = "python3 -c \'print(999)\'"', "check must contain only"),
        # Dropping the secrets leaf hollows the gate exactly like dropping self-test does.
        ("mise.toml", 'depends = ["validate", "test", "self-test", "secrets"]', 'depends = ["validate", "test", "self-test"]', "check must contain only"),
        # The secrets task must stay the working-tree scan: the history verb is a separate
        # consent-requiring pre-publish step, and silently widening it here is drift.
        ("mise.toml", 'run = "betterleaks dir . --config .config/betterleaks.toml"', 'run = "betterleaks git . --config .config/betterleaks.toml"', "secrets must contain only"),
        ("mise.toml", 'run = "betterleaks dir . --config .config/betterleaks.toml"', 'run = "true"', "secrets must contain only"),
        # Dropping --config re-opens the neutering route it exists to close: without the flag
        # the scanner auto-loads a drop-in .gitleaks.toml/.betterleaks.toml from cwd or a
        # GITLEAKS_CONFIG*/BETTERLEAKS_CONFIG* variable, so an untracked `useDefault = false`
        # replaces the ruleset while the scan still exits 0 and every fixture here stays green.
        ("mise.toml", 'run = "betterleaks dir . --config .config/betterleaks.toml"', 'run = "betterleaks dir ."', "secrets must contain only"),
        ("mise.toml", 'run_windows = "betterleaks dir . --config .config/betterleaks.toml"', 'run_windows = "betterleaks dir ."', "secrets must contain only"),
        # The pinned config is the other half of the same control: pinning only the flag would
        # leave an edit to the file it points at free to disable the default ruleset.
        (".config/betterleaks.toml", "useDefault = true", "useDefault = false", ".config/betterleaks.toml must contain only [extend] useDefault = true"),
        ("mise.toml", 'run = "uv run --python 3.12.11 --script scripts/validate_bundle.py"', 'run = "python3 scripts/validate_bundle.py"', "task validate.run must equal"),
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
        shutil.copytree(ROOT, repo, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
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
            b'[[tools.node]]\nversion = "22.22.3"',
            b'[[tools.node]]\nversion = "22.22.3"\nunexpected = "not generated"',
        )

    def test_current_gate_graph_is_valid(self) -> None:
        result = self.run_validator(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
            self.assertIn("mise.lock tools must equal", result.stderr)

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
            (b'[[tools.node]]\nversion = "22.22.3"', b'[[tools.node]]\nversion = "22.22.2"'),
            (b'[[tools.bun]]\nversion = "1.3.10"', b'[[tools.bun]]\nversion = "1.3.9"'),
            (
                b'[[tools."npm:@os-eco/seeds-cli"]]\nversion = "0.5.14"',
                b'[[tools."npm:@os-eco/seeds-cli"]]\nversion = "0.5.13"',
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

        # The gate is wired: one task, the working-tree verb, inside check's dependency chain.
        # --config is asserted here too, because an invocation that can be silently repointed at
        # a drop-in ruleset is wired in name only.
        secrets = config["tasks"]["secrets"]
        self.assertEqual(secrets["run"], "betterleaks dir . --config .config/betterleaks.toml")
        self.assertEqual(secrets["run_windows"], secrets["run"])
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
