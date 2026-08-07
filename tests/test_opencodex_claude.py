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
        ocx_exit: int = 0,
        provider_list_json: object | None = None,
        catalog_json: object | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "calls.log"
        mise = bin_dir / "mise"
        # `provider list --json` and `health --json` are answered from fixtures so the
        # configured-vs-live comparison can be driven from the test. Everything else is
        # recorded to the call log and exits with OCX_EXIT.
        mise.write_text(
            "#!/bin/sh\n"
            "while [ \"$#\" -gt 0 ] && [ \"$1\" != -- ]; do shift; done\n"
            "[ \"${1:-}\" = -- ] && shift\n"
            "case \"${1:-} ${2:-} ${3:-}\" in\n"
            "  'ocx --version ') exit 0 ;;\n"
            "  'ocx health ') exit 0 ;;\n"
            "  'ocx health --json') printf '{\"ok\":true,\"pid\":4242,\"port\":10100}\\n'; exit 0 ;;\n"
            "  'ocx config get') [ -n \"${AUTH_MODE:-}\" ] && printf '%s\\n' \"$AUTH_MODE\"; exit 0 ;;\n"
            "  'ocx config show') printf '%s\\n' \"$CONFIG_JSON\"; exit 0 ;;\n"
            "  'ocx provider list') \n"
            "    if [ \"${4:-}\" = --json ] || [ \"${3:-}\" = --json ]; then\n"
            "      printf '%s\\n' \"$PROVIDER_LIST_JSON\"; exit 0\n"
            "    fi\n"
            "    printf 'Configured providers:\\n\\nAvailable from registry\\n'; exit 0 ;;\n"
            "esac\n"
            "printf '<%s>' \"$@\" >> \"$CALL_LOG\"\n"
            "printf '\\n' >> \"$CALL_LOG\"\n"
            "exit ${OCX_EXIT:-0}\n"
        )
        mise.chmod(0o755)
        # curl stub: serves the gateway catalog fixture for /v1/models and fails for
        # /healthz so uptime stays a nicety. CATALOG_JSON empty => unreachable catalog.
        curl = bin_dir / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            "for argument in \"$@\"; do\n"
            "  case \"$argument\" in\n"
            "    */v1/models)\n"
            "      [ -n \"${CATALOG_JSON:-}\" ] || exit 22\n"
            "      printf '%s\\n' \"$CATALOG_JSON\"; exit 0 ;;\n"
            "  esac\n"
            "done\n"
            "exit 22\n"
        )
        curl.chmod(0o755)
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
            "OCX_EXIT": str(ocx_exit),
            "CONFIG_JSON": json.dumps(config if config is not None else {"providers": {}}),
            "PROVIDER_LIST_JSON": json.dumps(
                provider_list_json if provider_list_json is not None else {"configured": []}
            ),
            "CATALOG_JSON": "" if catalog_json is None else json.dumps(catalog_json),
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

    def test_configure_refuses_mixed_case_renamed_anthropic_provider(self) -> None:
        config = {
            "providers": {
                "Research-Vendor": {
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

    # --- Muse-as-a-provider: the gateway route ------------------------------------------
    #
    # `provider add muse --base-url https://api.meta.ai/v1` is the executed registration. It
    # must be admitted on the explicit-non-Anthropic-endpoint rule, since `muse` is not in the
    # upstream registry roster.

    def test_configure_allows_muse_provider_add_with_meta_endpoint(self) -> None:
        result, log = self.run_launcher(
            "configure", "provider", "add", "muse", "--adapter", "openai-responses",
            "--base-url", "https://api.meta.ai/v1", "--default-model", "muse-spark-1.2",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><provider><add><muse>", log.read_text())

    def test_configure_allows_provider_test_for_non_anthropic(self) -> None:
        config = {"providers": {"muse": {"baseUrl": "https://api.meta.ai/v1"}}}
        result, log = self.run_launcher("configure", "provider", "test", "muse", config=config)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><provider><test><muse>", log.read_text())

    def test_configure_refuses_provider_test_for_anthropic(self) -> None:
        result, log = self.run_launcher("configure", "provider", "test", "anthropic")

        self.assertEqual(result.returncode, 3)
        self.assertFalse(log.exists())

    # --- the sequencing hazard ----------------------------------------------------------

    def test_provider_mutation_prints_required_sync_and_restart(self) -> None:
        for arguments in (
            ("provider", "add", "muse", "--base-url", "https://api.meta.ai/v1"),
            ("provider", "edit", "custom-vendor", "--base-url", "https://models.example.test/v1"),
            ("provider", "remove", "custom-vendor"),
        ):
            with self.subTest(arguments=arguments):
                config = {"providers": {
                    "muse": {"baseUrl": "https://api.meta.ai/v1"},
                    "custom-vendor": {"baseUrl": "https://models.example.test/v1"},
                }}
                result, _ = self.run_launcher("configure", *arguments, config=config)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("NOT LIVE YET", result.stdout)
                self.assertIn("ocx sync", result.stdout)
                self.assertIn("restart", result.stdout)
                self.assertIn("default-provider", result.stdout)

    def test_read_only_route_prints_no_sync_notice(self) -> None:
        config = {"providers": {"muse": {"baseUrl": "https://api.meta.ai/v1"}}}
        for arguments in (
            ("provider", "list"),
            ("provider", "test", "muse"),
            ("models", "list"),
        ):
            with self.subTest(arguments=arguments):
                result, _ = self.run_launcher("configure", *arguments, config=config)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("NOT LIVE YET", result.stdout)

    def test_failed_mutation_prints_no_sync_notice(self) -> None:
        # A sync instruction after a write that did not land is a false instruction.
        config = {"providers": {"muse": {"baseUrl": "https://api.meta.ai/v1"}}}
        result, _ = self.run_launcher(
            "configure", "provider", "add", "muse", "--base-url", "https://api.meta.ai/v1",
            config=config, ocx_exit=1,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("NOT LIVE YET", result.stdout)

    def test_argv_credential_warns_without_echoing_the_value(self) -> None:
        secret = "OCX_TEST_SECRET"
        result, log = self.run_launcher(
            "configure", "provider", "add", "custom-vendor",
            "--base-url", "https://models.example.test/v1", "--api-key", secret,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING", result.stderr)
        self.assertIn("account add-key", result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        # A warning, never a refusal: upstream `provider add` has no stdin alternative.
        self.assertTrue(log.exists())

    def test_no_argv_credential_warning_without_a_key_flag(self) -> None:
        result, _ = self.run_launcher(
            "configure", "provider", "add", "custom-vendor",
            "--base-url", "https://models.example.test/v1",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("WARNING", result.stderr)

    # --- status: configured vs LIVE catalog ---------------------------------------------

    def test_status_reports_not_live_provider(self) -> None:
        result, _ = self.run_launcher(
            "status",
            provider_list_json={"configured": [
                {"name": "openai", "isDefault": True},
                {"name": "muse", "isDefault": False},
            ]},
            catalog_json={"data": [{"id": "gpt-5.6-terra"}]},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NOT-LIVE", result.stdout)
        self.assertIn("muse", result.stdout)
        self.assertIn("default-provider", result.stdout)

    def test_status_reports_ok_when_configured_provider_is_served(self) -> None:
        result, _ = self.run_launcher(
            "status",
            provider_list_json={"configured": [
                {"name": "openai", "isDefault": True},
                {"name": "muse", "isDefault": False},
            ]},
            catalog_json={"data": [
                {"id": "gpt-5.6-terra"},
                {"id": "muse/muse-spark-1.2"},
            ]},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("every configured provider is served", result.stdout)
        self.assertNotIn("NOT-LIVE", result.stdout)

    def test_status_never_flags_the_default_provider_as_not_live(self) -> None:
        # The default provider serves BARE ids, so there is no `openai/` prefix to match.
        # Reporting it NOT-LIVE would be a false alarm on every healthy gateway.
        result, _ = self.run_launcher(
            "status",
            provider_list_json={"configured": [{"name": "openai", "isDefault": True}]},
            catalog_json={"data": [{"id": "gpt-5.6-terra"}]},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("NOT-LIVE", result.stdout)

    def test_status_degrades_to_unknown_when_catalog_is_unreadable(self) -> None:
        # An unreachable catalog must not be reported as either live or NOT-LIVE.
        result, _ = self.run_launcher(
            "status",
            provider_list_json={"configured": [
                {"name": "openai", "isDefault": True},
                {"name": "muse", "isDefault": False},
            ]},
            catalog_json=None,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unknown", result.stdout)
        self.assertNotIn("NOT-LIVE", result.stdout)


if __name__ == "__main__":
    unittest.main()
