from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "opencodex-claude.sh"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "bash is required")
class OpenCodexClaudeTests(unittest.TestCase):
    def run_launcher(
        self,
        *arguments: str,
        auth_mode: str = "",
        config: object | None = None,
        stdin: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "calls.log"
        mise = bin_dir / "mise"
        mise.write_text(
            "#!/bin/sh\n"
            "while [ \"$#\" -gt 0 ] && [ \"$1\" != -- ]; do shift; done\n"
            "[ \"${1:-}\" = -- ] && shift\n"
            "case \"${1:-} ${2:-} ${3:-}\" in\n"
            "  'ocx --version ') exit 0 ;;\n"
            "  'ocx health ') exit 0 ;;\n"
            "  'ocx config get') [ -n \"${AUTH_MODE:-}\" ] && printf '%s\\n' \"$AUTH_MODE\"; exit 0 ;;\n"
            "  'ocx config show') printf '%s\\n' \"$CONFIG_JSON\"; exit 0 ;;\n"
            "esac\n"
            "printf '<%s>' \"$@\" >> \"$CALL_LOG\"\n"
            "printf '\\n' >> \"$CALL_LOG\"\n"
            "exit 0\n"
        )
        mise.chmod(0o755)
        jq = shutil.which("jq")
        if jq:
            (bin_dir / "jq").symlink_to(jq)
        claude = bin_dir / "claude"
        claude.write_text("#!/bin/sh\nexit 0\n")
        claude.chmod(0o755)
        env = {
            "HOME": str(root / "home"),
            "XDG_STATE_HOME": str(root / "state"),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "CALL_LOG": str(log),
            "AUTH_MODE": auth_mode,
            "CONFIG_JSON": json.dumps(config if config is not None else {"providers": {}}),
        }
        result = subprocess.run(
            [BASH, str(SCRIPT), *arguments],
            input=stdin,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        return result, log

    def test_ultracode_injects_exact_setting_and_preserves_arguments(self) -> None:
        result, log = self.run_launcher("launch-ultracode", "--model", "gpt-5.6-sol")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude><--settings><{\"ultracode\":true}><--model><gpt-5.6-sol>", log.read_text())

    def test_ultracode_refuses_competing_settings_before_ocx(self) -> None:
        result, log = self.run_launcher("launch-ultracode", "--settings", "{}")

        self.assertEqual(result.returncode, 3)
        self.assertIn("REFUSED", result.stderr)
        self.assertFalse(log.exists())

    def test_ultracode_refuses_permission_bypass_before_ocx(self) -> None:
        for arguments in (
            ("--dangerously-skip-permissions",),
            ("--permission-mode=bypassPermissions",),
            ("--permission-mode", "bypassPermissions"),
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("launch-ultracode", *arguments)
                self.assertEqual(result.returncode, 3)
                self.assertFalse(log.exists())

    def test_explicit_subscription_marker_mode_is_refused_before_gateway(self) -> None:
        result, log = self.run_launcher("launch", auth_mode="subscription")

        self.assertEqual(result.returncode, 3)
        self.assertIn("explicitly subscription", result.stderr)
        self.assertFalse(log.exists())

    def test_ordinary_launch_keeps_argument_boundaries(self) -> None:
        result, log = self.run_launcher("launch", "--settings", '{"custom":true}', "two words")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude><--settings><{\"custom\":true}><two words>", log.read_text())

    def test_launch_does_not_print_forwarded_secret(self) -> None:
        secret = "OCX_TEST_SECRET"
        result, _ = self.run_launcher("launch", "--settings", f'{{"token":"{secret}"}}')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.stderr)

    def test_configure_refuses_anthropic_aliases_case_insensitively(self) -> None:
        cases = (
            ("login", "anthropic"),
            ("LoGiN", "AnThRoPiC"),
            ("logout", "anthropic_key"),
            ("provider", "add", "anthropic-apikey"),
            ("provider", "remove", "claude"),
            ("account", "add-key", "anthropic-key"),
            ("account", "reauth", "CLAUDE-AI"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("configure", *arguments)
                self.assertEqual(result.returncode, 3)
                self.assertIn("REFUSED", result.stderr)
                self.assertFalse(log.exists())

    def test_configure_refuses_custom_anthropic_endpoint_without_printing_secret(self) -> None:
        secret = "OCX_TEST_SECRET"
        result, log = self.run_launcher(
            "configure", "provider", "add", "harmless-name",
            "--adapter", "openai-chat", "--base-url", "HTTPS://API.ANTHROPIC.COM:443/v1",
            "--api-key", secret,
        )

        self.assertEqual(result.returncode, 3)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertFalse(log.exists())

    def test_configure_refuses_renamed_anthropic_provider(self) -> None:
        config = {
            "providers": {
                "research-vendor": {
                    "adapter": "anthropic",
                    "baseUrl": "https://api.anthropic.com",
                }
            }
        }
        result, log = self.run_launcher(
            "configure", "account", "add-key", "research-vendor", config=config
        )

        self.assertEqual(result.returncode, 3)
        self.assertFalse(log.exists())

    def test_configure_refuses_unbounded_and_unknown_routes(self) -> None:
        cases = (
            ("setup",),
            ("init",),
            ("gui",),
            ("config", "set", "providers.openrouter.apiKey", "value"),
            ("config", "import", "candidate.json", "--yes"),
            ("provider", "future-mutation", "openrouter"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("configure", *arguments)
                self.assertEqual(result.returncode, 3)
                self.assertFalse(log.exists())

    def test_configure_allows_non_anthropic_provider_and_preserves_arguments(self) -> None:
        result, log = self.run_launcher("configure", "login", "xai", "two words")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><login><xai><two words>", log.read_text())

    def test_configure_allows_third_party_anthropic_wire_adapter(self) -> None:
        result, log = self.run_launcher(
            "configure", "provider", "add", "xiaomi", "--adapter", "anthropic",
            "--base-url", "https://api.xiaomimimo.com/anthropic",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><provider><add><xiaomi>", log.read_text())

    def test_configure_allows_custom_non_anthropic_endpoint_without_printing_secret(self) -> None:
        secret = "OCX_TEST_SECRET"
        result, log = self.run_launcher(
            "configure", "provider", "add", "custom-vendor", "--base-url",
            "https://models.example.test/v1", "--api-key", secret,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertTrue(log.exists())

    def test_configure_allows_masked_inspection(self) -> None:
        cases = (
            ("provider", "list"),
            ("provider", "show", "anthropic"),
            ("account", "list", "anthropic"),
            ("config", "show", "--json"),
            ("config", "get", "providers.anthropic"),
            ("config", "validate"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, _ = self.run_launcher("configure", *arguments)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
