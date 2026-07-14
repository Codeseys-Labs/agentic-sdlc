from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
VALIDATOR = Path("scripts/validate_bundle.py")


class GateGraphTests(unittest.TestCase):
    TOOLCHAIN_MUTATIONS = (
        ("mise.toml", 'node = "22.22.3"', 'node = "22.22.2"', "mise.toml tools must equal"),
        ("mise.toml", 'bun = "1.3.10"', 'bun = "1.3.9"', "mise.toml tools must equal"),
        ("mise.toml", 'version = "0.5.14"', 'version = "0.5.13"', "mise.toml tools must equal"),
        ("mise.toml", 'package_manager = "npm"', 'package_manager = "bun"', "npm.package_manager must equal npm"),
        ("mise.toml", 'depends = ["node"]', 'depends = []', "Seeds tool must depend on node"),
    )

    LOCKED_TOOLCHAIN = {
        "node": {"version": "22.22.3", "backend": "core:node"},
        "bun": {"version": "1.3.10", "backend": "core:bun"},
        "npm:@os-eco/seeds-cli": {"version": "0.5.14", "backend": "npm:@os-eco/seeds-cli"},
    }

    MUTATIONS = (
        ("mise.toml", 'depends = ["validate", "test", "self-test"]', 'depends = ["validate", "test"]', "check must contain only"),
        ("mise.toml", 'depends = ["validate", "test", "self-test"]', 'depends = ["validate", "test", "self-test"]\nrun = "python3 -c \'print(999)\'"', "check must contain only"),
        ("mise.toml", 'run = "uv run --python 3.12.11 --script scripts/validate_bundle.py"', 'run = "python3 scripts/validate_bundle.py"', "task validate.run must equal"),
        ("mise.toml", 'min_version = "2026.4.27"', 'min_version = "2025.1.0"', "must require mise 2026.4.27"),
        ("scripts/validate-bundle.sh", 'exec mise -C "$root" exec -- uv run --python 3.12.11', "exec python3", "exec-only pinned mise/uv wrapper"),
        ("scripts/bump-version.sh", 'mise -C "$repo_root" exec -- uv run --python 3.12.11 python - "$manifest"', '# mise -C "$repo_root" exec -- uv run --python 3.12.11 python -\npython3 - "$manifest"', "bump-version.sh must use only"),
        ("scripts/bump-version.sh", "\nPY\n", "\nPY\npython3 -c 'print(1)'\n", "must end at the pinned Python heredoc"),
        ("lefthook.yml", "run: mise run self-test", "run: mise run check", "documented best-effort gate subsets"),
        ("mise.lock", '[tools.uv."platforms.windows-x64"]', '[tools.uv."platforms.windows-arm64"]', "mise.lock uv platforms must equal"),
        ("mise.lock", "https://github.com/astral-sh/uv/releases/download/0.11.17/uv-x86_64-unknown-linux-musl.tar.gz", "https://evil.invalid/uv", "mise.lock uv linux-x64 URL must equal"),
        ("mise.lock", "sha256:4231a429d4e0f7c1937d8916658c08a7706cd7872afebeb87203a18c2e0dc28e", "sha256:" + "0" * 64, "checksum must equal the generated lock"),
        ("mise.lock", 'backend = "aqua:astral-sh/uv"', 'backend = "aqua:attacker/uv"', "mise.lock uv backend must equal"),
        ("mise.lock", 'provenance = "github-attestations"', 'provenance = "unverified"', "provenance must equal github-attestations"),
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
                if name == "npm:@os-eco/seeds-cli":
                    self.assertEqual(set(entries[0]), {"version", "backend"})
                else:
                    expected_platforms = {
                        "node": {"linux-x64", "macos-arm64", "macos-x64", "windows-x64"},
                        "bun": {
                            "linux-x64", "linux-x64-baseline", "linux-x64-musl", "linux-x64-musl-baseline",
                            "macos-arm64", "macos-x64", "macos-x64-baseline", "windows-x64", "windows-x64-baseline",
                        },
                    }[name]
                    self.assertEqual(platform_keys, {f"platforms.{platform}" for platform in expected_platforms})
                    for key in platform_keys:
                        self.assertEqual(set(entries[0][key]), {"checksum", "url"})

    def test_toolchain_lock_mutations_fail(self) -> None:
        mutations = (
            ("node", 'version = "22.22.3"', 'version = "22.22.2"', "mise.lock must resolve node 22.22.3"),
            ("bun", 'version = "1.3.10"', 'version = "1.3.9"', "mise.lock must resolve bun 1.3.10"),
            ("npm:@os-eco/seeds-cli", 'version = "0.5.14"', 'version = "0.5.13"', "mise.lock must resolve npm:@os-eco/seeds-cli 0.5.14"),
            ("npm:@os-eco/seeds-cli", 'backend = "npm:@os-eco/seeds-cli"', 'backend = "core:node"', "mise.lock npm:@os-eco/seeds-cli backend must equal npm:@os-eco/seeds-cli"),
            ("node", "checksum = ", 'checksum = "sha256:' + "0" * 64 + '" # ', "mise.lock node linux-x64 checksum must equal the generated lock"),
            ("bun", "checksum = ", 'checksum = "sha256:' + "0" * 64 + '" # ', "mise.lock bun linux-x64 checksum must equal the generated lock"),
            ("npm:@os-eco/seeds-cli", 'backend = "npm:@os-eco/seeds-cli"', 'backend = "npm:@os-eco/seeds-cli"\ntransitive_integrity = "unsupported"', "must contain version and backend only"),
        )
        executed = 0
        for name, old, new, diagnostic in mutations:
            with self.subTest(tool=name, diagnostic=diagnostic), tempfile.TemporaryDirectory() as temp:
                repo = self.copied_repo(temp)
                path = repo / "mise.lock"
                text = path.read_text(encoding="utf-8")
                heading = f"[[tools.{name}]]" if ":" not in name else f'[[tools."{name}"]]'
                start = text.find(heading)
                self.assertNotEqual(start, -1)
                end = text.find("\n[[tools.", start + len(heading))
                if end == -1:
                    end = len(text)
                section = text[start:end]
                self.assertIn(old, section)
                path.write_text(text[:start] + section.replace(old, new, 1) + text[end:], encoding="utf-8")
                result = self.run_validator(repo)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(diagnostic, result.stderr)
                executed += 1
        self.assertEqual(executed, len(mutations))

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


if __name__ == "__main__":
    unittest.main()
