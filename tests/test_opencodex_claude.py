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
        subscription_status: object | None = None,
        native_passthrough: str = "",
        anthropic_base_url: str = "",
        config_diagnostics: object | None = None,
        healthy: bool = True,
        config: object | None = None,
        stdin: str | None = None,
        ocx_exit: int = 0,
        provider_list_json: object | None = None,
        catalog_json: object | None = None,
        global_settings: object | None = None,
        global_session_entries: bool = False,
        preset_isolated_settings: object | None = None,
        preset_isolated_projects: bool = False,
        parent_env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        # A fake global ~/.claude, so selective session inheritance (ADR-0010) can be exercised
        # without ever reading or touching the real operator's config dir.
        self.home = root / "home"
        self.global_claude = self.home / ".claude"
        self.isolated = root / "state" / "agentic-sdlc" / "ocx-claude"
        if global_settings is not None:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "settings.json").write_text(json.dumps(global_settings))
        if global_session_entries:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "history.jsonl").write_text('{"display":"real prompt"}\n')
            (self.global_claude / "projects" / "demo").mkdir(parents=True, exist_ok=True)
            (self.global_claude / "projects" / "demo" / "session.jsonl").write_text("{}\n")
            (self.global_claude / "shell-snapshots").mkdir(exist_ok=True)
        if preset_isolated_settings is not None:
            self.isolated.mkdir(parents=True, exist_ok=True)
            (self.isolated / "settings.json").write_text(json.dumps(preset_isolated_settings))
        if preset_isolated_projects:
            (self.isolated / "projects" / "local").mkdir(parents=True, exist_ok=True)
            (self.isolated / "projects" / "local" / "session.jsonl").write_text("plane-local\n")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        # KNOWN PRE-EXISTING DEFECT, deliberately NOT fixed here so it stays separable from the
        # ADR-0014 refactor. Nothing writes `calls.log`; the mise stub appends to OCX_TRACE_LOG.
        # So `log.read_text()` raises FileNotFoundError (9 tests) and `assertFalse(log.exists())`
        # passes vacuously. Setting `log = self.ocx_trace_log` repairs the readers but then fails
        # 11 refusal tests whose real intent is "no ocx MUTATION ran", not "no ocx call at all" --
        # `require_ocx` legitimately runs `ocx --version` first. Fixing it means rewriting each of
        # those assertions against the trace CONTENT. Do that as its own change.
        log = root / "calls.log"
        self.ocx_trace_log = root / "ocx-trace.log"
        mise = bin_dir / "mise"
        # Record every `ocx` invocation before fixture dispatch, so tests can prove exact
        # preflight ordering instead of mistaking an unlogged special case for no interaction.
        # Pinned `jq` resolution is a separate tool call and is not part of the gateway log.
        mise.write_text(
            "#!/bin/sh\n"
            "while [ \"$#\" -gt 0 ] && [ \"$1\" != -- ]; do shift; done\n"
            "[ \"${1:-}\" = -- ] && shift\n"
            "if [ \"${1:-}\" = jq ]; then shift; exec \"${TEST_REAL_JQ:-jq}\" \"$@\"; fi\n"
            "printf '<%s>' \"$@\" >> \"$OCX_TRACE_LOG\"\n"
            "printf '\\n' >> \"$OCX_TRACE_LOG\"\n"
            "case \"${1:-} ${2:-} ${3:-}\" in\n"
            "  'ocx --version ') exit 0 ;;\n"
            "  'ocx health ') exit ${HEALTHY:-0} ;;\n"
            "  'ocx health --json') [ \"${HEALTHY:-0}\" -eq 0 ] || exit \"${HEALTHY:-0}\"; printf '{\"ok\":true,\"pid\":4242,\"port\":10100}\\n'; exit 0 ;;\n"
            "  'ocx claude config') printf '%s\\n' \"$SUBSCRIPTION_STATUS\"; exit 0 ;;\n"
            "  'ocx config get')\n"
            "    case \"${4:-}\" in\n"
            "      claudeCode.nativePassthrough) [ -n \"${NATIVE_PASSTHROUGH:-}\" ] && { printf '%s\\n' \"$NATIVE_PASSTHROUGH\"; exit 0; } ;;\n"
            "      claudeCode.anthropicBaseUrl) [ -n \"${OCX_TEST_ANTHROPIC_BASE_URL_SETTING:-}\" ] && { printf '%s\\n' \"$OCX_TEST_ANTHROPIC_BASE_URL_SETTING\"; exit 0; } ;;\n"
            "    esac\n"
            "    [ -n \"${AUTH_MODE:-}\" ] && { printf '%s\\n' \"$AUTH_MODE\"; exit 0; }\n"
            "    case \"${4:-}\" in providers.anthropic) exit 0 ;; esac\n"
            "    printf 'config path not found: %s\\n' \"${4:-}\" >&2; exit 2 ;;\n"
            "  'ocx config show')\n"
            "    case \" $* \" in *' --source '*) printf '%s\\n' \"$CONFIG_DIAGNOSTICS\" ;; *) printf '%s\\n' \"$CONFIG_JSON\" ;; esac\n"
            "    exit 0 ;;\n"
            "  'ocx provider list') \n"
            "    if [ \"${4:-}\" = --json ] || [ \"${3:-}\" = --json ]; then\n"
            "      printf '%s\\n' \"$PROVIDER_LIST_JSON\"; exit 0\n"
            "    fi\n"
            "    printf 'Configured providers:\\n\\nAvailable from registry\\n'; exit 0 ;;\n"
            "esac\n"
            # Forward the ordinary route to stub `claude` so its child environment is observable.
            "if [ \"${1:-} ${2:-}\" = 'ocx claude' ]; then shift 2; exec claude \"$@\"; fi\n"
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
        # Records the environment it actually received, so the ADR-0010 env policy can be
        # asserted per class against the REAL child environment rather than against the script's
        # source. The log variable is deliberately not named CLAUDE_*/ANTHROPIC_*/AWS_*: the
        # scrub would take a stub's own log path with it.
        claude.write_text(
            "#!/bin/sh\n"
            'if [ -n "${OCX_TEST_ENV_LOG:-}" ]; then env | sort > "$OCX_TEST_ENV_LOG"; fi\n'
            'if [ -n "${OCX_TEST_ARGV_LOG:-}" ]; then for argument in "$@"; do printf "<%s>" "$argument"; done > "$OCX_TEST_ARGV_LOG"; fi\n'
            "exit 0\n"
        )
        claude.chmod(0o755)
        # `ocx claude ...` must reach the stub `claude` for the env log to exist, so the mise stub
        # forwards that one route instead of only recording it.
        self.env_log = root / "child-env.txt"
        self.argv_log = root / "child-argv.txt"
        env = {
            "HOME": str(root / "home"),
            "XDG_STATE_HOME": str(root / "state"),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "OCX_TRACE_LOG": str(self.ocx_trace_log),
            "AUTH_MODE": auth_mode,
            "OCX_EXIT": str(ocx_exit),
            "CONFIG_JSON": json.dumps(config if config is not None else {"providers": {}}),
            "PROVIDER_LIST_JSON": json.dumps(
                provider_list_json if provider_list_json is not None else {"configured": []}
            ),
            "CATALOG_JSON": "" if catalog_json is None else json.dumps(catalog_json),
            "OCX_TEST_ENV_LOG": str(self.env_log),
            "OCX_TEST_ARGV_LOG": str(self.argv_log),
            "SUBSCRIPTION_STATUS": json.dumps(subscription_status if subscription_status is not None else {
                "enabled": True, "authMode": "auto", "markerMode": "subscription",
                "authModeOrigin": "auto-present", "admissionKeyActive": False,
                "authDetectionUnknown": False, "authFoundBy": "claude-credentials-file", "modelMap": {},
            }),
            "CONFIG_DIAGNOSTICS": json.dumps(
                config_diagnostics
                if config_diagnostics is not None
                else {"config": {}, "source": "default", "error": None, "warnings": []}
            ),
            "NATIVE_PASSTHROUGH": native_passthrough,
            "OCX_TEST_ANTHROPIC_BASE_URL_SETTING": anthropic_base_url,
            "HEALTHY": "0" if healthy else "1",
            # Absolute path, so the mise stub can serve `mise exec -- jq` even from a PATH that
            # deliberately has no jq on it.
            "TEST_REAL_JQ": shutil.which("jq") or "jq",
        }
        if parent_env:
            env.update(parent_env)
        # Kept so a test can launch a SECOND time against the same home and state root, which
        # is how "a stanza removed globally is dropped from the plane" is exercised.
        self.launch_env = env
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

    def test_ordinary_launch_keeps_argument_boundaries(self) -> None:
        result, log = self.run_launcher("launch", "--settings", '{"custom":true}', "two words")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude><--settings><{\"custom\":true}><two words>", log.read_text())

    def test_ensure_checks_health_without_launching_claude(self) -> None:
        result, log = self.run_launcher("ensure")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("healthy", result.stdout)
        self.assertIn("does not launch Claude Code", result.stdout)
        self.assertFalse(self.env_log.exists(), "ensure must not launch the Claude child")
        self.assertFalse(log.exists(), "an already healthy gateway needs no mutating ocx route")

    def test_ensure_rejects_arguments_before_contacting_gateway(self) -> None:
        result, log = self.run_launcher("ensure", "unexpected")

        self.assertEqual(result.returncode, 2)
        self.assertIn("takes no arguments", result.stderr)
        self.assertFalse(log.exists())
        self.assertFalse(self.env_log.exists())

    def test_launch_help_distinguishes_plain_claude_from_ccodex(self) -> None:
        result, log = self.run_launcher("launch", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plain `claude`", result.stdout)
        self.assertIn("talks to Anthropic directly and does not involve this gateway", result.stdout)
        # ADR-0014: the distinction is no longer Anthropic-vs-not, it is one-catalog-vs-both.
        self.assertIn("both catalogs in one session", result.stdout)
        self.assertFalse(log.exists())

    def test_launch_does_not_print_forwarded_secret(self) -> None:
        secret = "OCX_TEST_SECRET"
        result, _ = self.run_launcher("launch", "--settings", f'{{"token":"{secret}"}}')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.stderr)

    # --- ADR-0014 route integrity ----------------------------------------------------------
    #
    # `launch` no longer scrubs or isolates anything: preserving the operator's own login is the
    # whole point. What it must still catch is a setting that makes the launch a NO-OP which
    # still looks routed. The first case below was measured on a real host on 2026-08-10: with
    # CLAUDE_CODE_USE_BEDROCK in the global settings env, a request never reached a local
    # capture listener and was still answered, because Bedrock consults ANTHROPIC_BEDROCK_BASE_URL
    # rather than ANTHROPIC_BASE_URL.

    def test_launch_refuses_a_provider_routing_variable_that_bypasses_the_gateway(self) -> None:
        for name in ("CLAUDE_CODE_USE_BEDROCK", "AWS_BEARER_TOKEN_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
            with self.subTest(name=name):
                result, _ = self.run_launcher("launch", parent_env={name: "1"})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                # It must not claim to have routed anything it did not route.
                self.assertNotIn("routed at", result.stdout)

    def test_launch_refuses_a_bypassing_key_in_the_global_settings_document(self) -> None:
        # The channel an operator forgets: settings.json env is read on every launch and
        # survives a clean shell, so checking only the exported environment is not enough.
        result, _ = self.run_launcher(
            "launch", global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}}
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CLAUDE_CODE_USE_BEDROCK", result.stderr)
        self.assertIn("settings.json", result.stderr)

    def test_launch_refuses_an_apikeyhelper_that_would_displace_the_login(self) -> None:
        result, _ = self.run_launcher("launch", global_settings={"apiKeyHelper": "/bin/echo"})

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("apiKeyHelper", result.stderr)

    def test_launch_refuses_a_console_key_without_echoing_it(self) -> None:
        # sk-ant-api* satisfies opencodex's bare sk-ant- passthrough gate, so it takes the SAME
        # native branch and bills API credits while looking like subscription traffic.
        secret = "sk-ant-api03-OCXTESTSENTINEL"
        result, _ = self.run_launcher("launch", parent_env={"ANTHROPIC_API_KEY": secret})

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("ANTHROPIC_API_KEY", result.stderr)
        self.assertIn("credits", result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_launch_accepts_a_subscription_shaped_oauth_token(self) -> None:
        # The inverse of the case above, and the one ADR-0003 used to refuse outright: an
        # sk-ant-oat* login is exactly what this route now exists to carry.
        result, _ = self.run_launcher(
            "launch", parent_env={"ANTHROPIC_AUTH_TOKEN": "sk-ant-oat01-OCXTESTSENTINEL"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)

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

    # --- selective session inheritance (ADR-0010) ---------------------------------------
    #
    # The operator's requirement is asymmetric: inert session DATA and the statusLine stanza
    # cross the plane boundary, credentials never do. These tests assert both halves, and the
    # credential half is asserted POSITIVELY -- a credential is planted in a fake global
    # settings.json and the constructed isolated file is proven not to contain it.

    # A global settings.json shaped like a real one: the statusLine to inherit, next to an
    # `env` block carrying a live-shaped Bedrock bearer token plus routing and model pins.
    CREDENTIAL_BEARING_GLOBAL_SETTINGS = {
        "env": {
            "AWS_BEARER_TOKEN_BEDROCK": "planted-bedrock-bearer-value",
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_REGION": "us-west-2",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "planted-model-pin",
        },
        "statusLine": {"type": "command", "command": "/global/statusline-command.sh"},
        "model": "planted-global-model",
        "apiKeyHelper": "/global/print-my-key.sh",
        "permissions": {"allow": ["Bash"]},
    }

    def child_env(self) -> dict[str, str]:
        recorded = self.env_log.read_text().splitlines()
        return dict(line.split("=", 1) for line in recorded if "=" in line)

    def jq_free_environment(self) -> dict[str, str]:
        """The stub environment with `jq` genuinely unreachable.

        Deleting the stub symlink is NOT enough: the harness PATH ends in `/usr/bin:/bin`, which
        supplies the developer's own `/usr/bin/jq`. A first attempt at these tests did exactly
        that and passed against the UNFIXED launcher, which is the same
        agree-with-this-machine failure the tests below exist to prevent. So the PATH is narrowed
        to the stub dir alone, and the handful of binaries the script genuinely needs are linked
        in from the real system by absolute path.
        """
        stub_bin = Path(self.launch_env["PATH"].split(":")[0])
        stub_jq = stub_bin / "jq"
        if stub_jq.exists() or stub_jq.is_symlink():
            stub_jq.unlink()
        for utility in (
            "sed", "tr", "cut", "grep", "date", "du", "mv", "ln", "mkdir", "cat", "rm",
            "dirname", "basename", "head", "tail", "sort", "wc", "readlink", "stat",
            "chmod", "cp", "id", "pgrep", "sleep", "env", "uname", "awk", "find", "ls",
        ):
            resolved = shutil.which(utility)
            target = stub_bin / utility
            if resolved and not target.exists() and not target.is_symlink():
                target.symlink_to(resolved)
        return {**self.launch_env, "PATH": str(stub_bin)}

    def test_a_configure_mutation_is_admitted_without_jq_on_path(self) -> None:
        # The defect: `configure account add-key muse` was REFUSED with
        # `anthropic-or-unclassifiable-provider` on a fresh host where muse was correctly
        # configured as a non-Anthropic provider, because classification could not run without
        # `jq`. A missing tool was reported as a rejected provider, sending the operator to
        # inspect a config that was already right.
        self.run_launcher(
            "status",
            config={"providers": {"muse": {"baseUrl": "https://api.meta.ai/v1"}}},
        )
        environment = self.jq_free_environment()

        result = subprocess.run(
            [BASH, str(SCRIPT), "configure", "account", "add-key", "muse"],
            text=True, capture_output=True, check=False, env=environment, input="",
        )

        self.assertNotIn("anthropic-or-unclassifiable-provider", result.stderr)
        self.assertIn("approved opencodex configuration route", result.stdout)

    def test_an_anthropic_provider_is_still_refused_without_jq(self) -> None:
        # The fix must not become a bypass: with `jq` reachable through mise, an Anthropic
        # provider is still classified and still refused under ADR-0003.
        self.run_launcher(
            "status",
            config={"providers": {"sneaky": {"baseUrl": "https://api.anthropic.com"}}},
        )
        environment = self.jq_free_environment()

        result = subprocess.run(
            [BASH, str(SCRIPT), "configure", "account", "add-key", "sneaky"],
            text=True, capture_output=True, check=False, env=environment, input="",
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("REFUSED", result.stderr)
        self.assertNotIn("approved opencodex configuration route", result.stdout)

    def test_the_jq_resolver_does_not_recurse_into_itself(self) -> None:
        # The resolver is a shell function NAMED `jq`, so probing with `command -v jq` would find
        # the function and recurse until the shell died. `type -P` searches PATH only. This is the
        # same shadowing class that let a stale `ccodex` shell function hide the installed binary.
        self.run_launcher("status", config={"providers": {}})
        result = subprocess.run(
            [BASH, str(SCRIPT), "status"],
            text=True, capture_output=True, check=False, env=self.jq_free_environment(),
        )

        self.assertNotIn("too many levels", result.stderr.lower())
        self.assertNotIn("recursion", result.stderr.lower())
        self.assertLess(result.returncode, 126, result.stderr)

    # Help must not be a side-effecting operation. These assert on OUTPUT, never on exit status
    # alone: with a stubbed `claude` that exits 0, an exit code cannot distinguish "printed
    # usage" from "launched Claude Code, which then exited cleanly".
    SIDE_EFFECT_MARKER = "preparing gateway-routed Claude Code"

    def test_verb_level_help_prints_usage_and_prepares_nothing(self) -> None:
        for arguments in (
            ["ensure", "--help"],
            ["launch", "--help"],
            ["launch", "-h"],
            ["launch", "help"],
            ["launch-ultracode", "--help"],
            ["launch-ultracode", "-h"],
            ["status", "--help"],
            ["restart", "--help"],
            ["configure", "--help"],
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher(*arguments, global_session_entries=True)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                # Nothing was prepared, nothing was linked, nothing was written, and the
                # gateway was never contacted.
                self.assertNotIn(self.SIDE_EFFECT_MARKER, result.stdout)
                self.assertFalse(log.exists(), "help must not invoke any ocx route")
                self.assertFalse((self.isolated / "history.jsonl").exists())

    def test_verb_help_names_how_to_reach_the_wrapped_tools_help(self) -> None:
        # A wrapper that intercepts an argument must say how to forward it, or the interception
        # is itself a capability removal.
        result, _ = self.run_launcher("launch", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-- --help", result.stdout)
        self.assertIn("claude --help", result.stdout)

    def test_the_forwarding_separator_reaches_claude_code(self) -> None:
        # The escape hatch must actually work: `launch -- --help` prepares a real session and
        # forwards --help verbatim, which is the pass-through form the help text promises.
        result, log = self.run_launcher("launch", "--", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.SIDE_EFFECT_MARKER, result.stdout)
        self.assertIn("<ocx><claude><--help>", log.read_text())

    def test_a_later_help_argument_is_still_forwarded(self) -> None:
        # Only the FIRST argument is inspected. A --help appearing after other arguments may be
        # a forwarded flag or a flag's value, and guessing would swallow an operator's argument.
        result, log = self.run_launcher("launch", "--model", "gpt-5.6-sol", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude><--model><gpt-5.6-sol><--help>", log.read_text())

    def test_ultracode_help_does_not_trip_its_own_settings_refusal(self) -> None:
        result, log = self.run_launcher("launch-ultracode", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("REFUSED", result.stderr)
        self.assertIn("ultracode", result.stdout)
        self.assertFalse(log.exists())

    def test_configure_help_verb_still_reaches_the_upstream_surface(self) -> None:
        # `ocx help <verb>` is the documented way to inspect upstream and is already an admitted
        # read-only route. Intercepting the bare word `help` there would remove the only route
        # that answers "what can upstream actually do".
        result, log = self.run_launcher("configure", "help", "provider")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><help><provider>", log.read_text())


if __name__ == "__main__":
    unittest.main()
