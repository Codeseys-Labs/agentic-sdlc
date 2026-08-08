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
            # Forward the launch route to the stub `claude` so the child environment is
            # observable. Recording argv alone could not prove what the child received.
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
            "exit 0\n"
        )
        claude.chmod(0o755)
        # `ocx claude ...` must reach the stub `claude` for the env log to exist, so the mise stub
        # forwards that one route instead of only recording it.
        self.env_log = root / "child-env.txt"
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
            "OCX_TEST_ENV_LOG": str(self.env_log),
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

    def test_statusline_is_inherited_into_a_constructed_settings_document(self) -> None:
        result, _ = self.run_launcher(
            "launch", global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads((self.isolated / "settings.json").read_text())
        self.assertEqual(
            document["statusLine"],
            {"type": "command", "command": "/global/statusline-command.sh"},
        )
        self.assertIn("statusLine", result.stdout)

    def test_planted_credential_never_reaches_the_isolated_settings(self) -> None:
        result, _ = self.run_launcher(
            "launch", global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        raw = (self.isolated / "settings.json").read_text()
        document = json.loads(raw)
        # The credential VALUE is absent, and so is every credential-shaped carrier key.
        self.assertNotIn("planted-bedrock-bearer-value", raw)
        self.assertNotIn("AWS_BEARER_TOKEN_BEDROCK", raw)
        self.assertNotIn("env", document)
        self.assertNotIn("apiKeyHelper", document)
        # Non-credential keys outside the allowlist are excluded too: this is an allowlist, so
        # a global `model` or `permissions` does not silently become plane policy.
        self.assertNotIn("permissions", document)
        self.assertNotIn("planted-global-model", raw)
        # Nor did it leak to the terminal.
        self.assertNotIn("planted-bedrock-bearer-value", result.stdout + result.stderr)

    def test_global_settings_file_is_never_copied_or_linked(self) -> None:
        result, _ = self.run_launcher(
            "launch", global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        isolated_settings = self.isolated / "settings.json"
        self.assertFalse(isolated_settings.is_symlink())
        self.assertNotEqual(
            isolated_settings.read_bytes(),
            (self.global_claude / "settings.json").read_bytes(),
        )

    def test_inert_session_entries_are_shared_by_symlink(self) -> None:
        result, _ = self.run_launcher("launch", global_session_entries=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in ("history.jsonl", "projects", "shell-snapshots"):
            with self.subTest(entry=entry):
                target = self.isolated / entry
                self.assertTrue(target.is_symlink(), f"{entry} should be shared by symlink")
                self.assertEqual(target.resolve(), (self.global_claude / entry).resolve())
        # The operator's real history is visible through the link, which is the whole point.
        self.assertIn("real prompt", (self.isolated / "history.jsonl").read_text())

    def test_a_write_through_the_shared_link_lands_in_the_global_store(self) -> None:
        # This is the "no divergence, no stale duplicate" property that made symlinks the
        # choice over copies. Concurrency safety comes from Claude Code's own realpath'd
        # history lock, which both planes therefore share; see ADR-0010.
        result, _ = self.run_launcher("launch", global_session_entries=True)
        self.assertEqual(result.returncode, 0, result.stderr)

        with (self.isolated / "history.jsonl").open("a") as handle:
            handle.write('{"display":"written in the gateway plane"}\n')

        self.assertIn(
            "written in the gateway plane",
            (self.global_claude / "history.jsonl").read_text(),
        )
        self.assertTrue((self.isolated / "history.jsonl").is_symlink())

    def test_credential_stores_are_never_shared(self) -> None:
        result, _ = self.run_launcher(
            "launch",
            global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS,
            global_session_entries=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in (".credentials.json", "sessions", "session-env", "plugins", "agents"):
            with self.subTest(entry=entry):
                self.assertFalse((self.isolated / entry).is_symlink())

    def test_missing_global_statusline_is_not_a_failure(self) -> None:
        result, _ = self.run_launcher("launch", global_settings={"model": "only-a-model"})

        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads((self.isolated / "settings.json").read_text())
        self.assertNotIn("statusLine", document)
        self.assertIn("no statusLine", result.stdout)

    def test_a_statusline_removed_globally_is_dropped_from_the_plane(self) -> None:
        result, _ = self.run_launcher(
            "launch", global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("statusLine", json.loads((self.isolated / "settings.json").read_text()))

        # Second launch against the SAME state root, with the stanza gone from the global file.
        (self.global_claude / "settings.json").write_text(json.dumps({"model": "m"}))
        again = subprocess.run(
            [BASH, str(SCRIPT), "launch"],
            text=True, capture_output=True, check=False,
            env={**self.launch_env},
        )

        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotIn("statusLine", json.loads((self.isolated / "settings.json").read_text()))

    def test_settings_written_by_the_plane_itself_survive_inheritance(self) -> None:
        # Claude Code writes theme/model into the isolated settings.json itself. Inheritance
        # merges over that document rather than clobbering the plane's own choices.
        self.isolated_preset = True
        result, _ = self.run_launcher(
            "launch",
            global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS,
            preset_isolated_settings={"theme": "dark", "model": "plane-chosen-model"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads((self.isolated / "settings.json").read_text())
        self.assertEqual(document["theme"], "dark")
        self.assertEqual(document["model"], "plane-chosen-model")
        self.assertIn("statusLine", document)

    # --- environment-variable policy (ADR-0010) -------------------------------------------
    #
    # Claude Code resolves shell environment ABOVE settings.json env, so the settings allowlist
    # alone does not close the boundary. These assert the REAL child environment, per class.

    def child_env(self) -> dict[str, str]:
        recorded = self.env_log.read_text().splitlines()
        return dict(line.split("=", 1) for line in recorded if "=" in line)

    def test_credential_exported_in_the_parent_shell_never_reaches_the_child(self) -> None:
        # The defect this replaces: the old scrub matched ^(ANTHROPIC|CLAUDE) only, so an
        # AWS_* credential exported in the operator's shell reached the child intact.
        result, _ = self.run_launcher(
            "launch",
            parent_env={
                "AWS_BEARER_TOKEN_BEDROCK": "leak-canary-bedrock",
                "AWS_REGION": "us-west-2",
                "ANTHROPIC_API_KEY": "sk-ant-api-planted",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        child = self.child_env()
        for name in ("AWS_BEARER_TOKEN_BEDROCK", "AWS_REGION", "ANTHROPIC_API_KEY"):
            self.assertNotIn(name, child)
        self.assertNotIn("leak-canary-bedrock", "\n".join(child.values()))
        self.assertNotIn("leak-canary-bedrock", result.stdout + result.stderr)

    def test_provider_routing_variables_never_reach_the_child(self) -> None:
        result, _ = self.run_launcher(
            "launch",
            parent_env={
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "ANTHROPIC_BASE_URL": "https://planted.bedrock.example",
                "ANTHROPIC_BEDROCK_BASE_URL": "https://planted.two.example",
                "ANTHROPIC_VERTEX_PROJECT_ID": "planted-project",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        child = self.child_env()
        for name in (
            "CLAUDE_CODE_USE_BEDROCK",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_BEDROCK_BASE_URL",
            "ANTHROPIC_VERTEX_PROJECT_ID",
        ):
            self.assertNotIn(name, child)
        self.assertNotIn("planted.bedrock.example", "\n".join(child.values()))

    def test_model_pins_and_forced_fallback_never_reach_the_child(self) -> None:
        result, _ = self.run_launcher(
            "launch",
            parent_env={
                "ANTHROPIC_MODEL": "planted-model",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "planted-opus",
                "ANTHROPIC_DEFAULT_FABLE_MODEL_SUPPORTED_CAPABILITIES": "planted-caps",
                "ANTHROPIC_CUSTOM_MODEL_OPTION": "planted-custom",
                "ANTHROPIC_SMALL_FAST_MODEL": "planted-small",
                "FALLBACK_FOR_ALL_PRIMARY_MODELS": "planted-fallback",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        child = self.child_env()
        for name in (
            "ANTHROPIC_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_FABLE_MODEL_SUPPORTED_CAPABILITIES",
            "ANTHROPIC_CUSTOM_MODEL_OPTION",
            "ANTHROPIC_SMALL_FAST_MODEL",
            "FALLBACK_FOR_ALL_PRIMARY_MODELS",
        ):
            self.assertNotIn(name, child)

    def test_inert_preferences_are_inherited_including_the_privacy_flags(self) -> None:
        # Set-to-activate semantics: dropping a SET DISABLE_TELEMETRY re-enables telemetry in the
        # launched plane, which is a privacy regression the operator never asked for.
        preferences = {
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "DO_NOT_TRACK": "1",
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
            "CLAUDE_CODE_ACCESSIBILITY": "1",
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "5000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        result, _ = self.run_launcher("launch", parent_env=preferences)

        self.assertEqual(result.returncode, 0, result.stderr)
        child = self.child_env()
        for name, value in preferences.items():
            with self.subTest(variable=name):
                self.assertEqual(child.get(name), value)

    def test_tls_downgrade_and_timeout_are_not_inherited(self) -> None:
        result, _ = self.run_launcher(
            "launch",
            parent_env={"NODE_TLS_REJECT_UNAUTHORIZED": "0", "API_TIMEOUT_MS": "99"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        child = self.child_env()
        self.assertNotIn("NODE_TLS_REJECT_UNAUTHORIZED", child)
        self.assertNotIn("API_TIMEOUT_MS", child)

    def test_unrecognized_claude_variable_is_dropped_rather_than_guessed_at(self) -> None:
        result, _ = self.run_launcher(
            "launch", parent_env={"CLAUDE_CODE_SOME_FUTURE_ROUTING_FLAG": "1"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("CLAUDE_CODE_SOME_FUTURE_ROUTING_FLAG", self.child_env())

    def test_config_dir_is_still_exported_to_the_child(self) -> None:
        # CLAUDE_CONFIG_DIR is CLAUDE_*-prefixed and is set by the launcher AFTER the scrub. If
        # the scrub ordering regressed, the child would silently use the operator's real
        # ~/.claude, which is the failure the whole split plane exists to prevent.
        result, _ = self.run_launcher("launch")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.child_env().get("CLAUDE_CONFIG_DIR"), str(self.isolated))

    def test_status_reports_the_policy_class_without_printing_values(self) -> None:
        result, _ = self.run_launcher(
            "status",
            parent_env={
                "AWS_BEARER_TOKEN_BEDROCK": "leak-canary-bedrock",
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "planted-opus",
                "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
            },
        )

        self.assertIn("environment-variable policy", result.stdout)
        self.assertIn("AWS_BEARER_TOKEN_BEDROCK", result.stdout)
        self.assertIn("credential class", result.stdout)
        self.assertIn("provider routing", result.stdout)
        self.assertIn("model pin", result.stdout)
        self.assertIn("INHERITED", result.stdout)
        # The classification is printed; no value ever is.
        self.assertNotIn("leak-canary-bedrock", result.stdout + result.stderr)
        self.assertNotIn("planted-opus", result.stdout + result.stderr)
        # The helper's own configuration is launcher state, not the operator's environment.
        self.assertNotIn("CLAUDE_SHARED_SESSION_ENTRIES", result.stdout)
        self.assertNotIn("CLAUDE_INHERITED_ENV_VARS", result.stdout)

    def test_post_condition_blocks_a_credential_even_if_the_allowlist_is_widened(self) -> None:
        # Defense in depth, and the reason the check is a post-condition on the CONSTRUCTED
        # document rather than a property of the allowlist: if a future edit admitted `env`,
        # the write must fail loudly instead of silently shipping the token.
        helper = Path(__file__).parents[1] / "assets" / "claude" / "session-inheritance.sh"
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        global_claude = root / "home" / ".claude"
        isolated = root / "iso"
        global_claude.mkdir(parents=True)
        isolated.mkdir()
        (global_claude / "settings.json").write_text(
            json.dumps({
                "env": {"AWS_BEARER_TOKEN_BEDROCK": "widened-allowlist-secret"},
                "statusLine": {"type": "command", "command": "/x.sh"},
            })
        )
        script = (
            f'. "{helper}"\n'
            'CLAUDE_INHERITED_SETTINGS_KEYS="statusLine env"\n'
            f'inherit_session_state "{isolated}" "{global_claude}"\n'
        )
        result = subprocess.run(
            [BASH, "-c", script], text=True, capture_output=True, check=False
        )

        self.assertIn("REFUSED to write", result.stdout + result.stderr)
        self.assertFalse((isolated / "settings.json").exists())
        self.assertNotIn("widened-allowlist-secret", result.stdout + result.stderr)

    def test_pre_existing_real_session_data_is_never_destroyed(self) -> None:
        # The ocx plane already held 102MB of real projects/ on the operator's host. A launch
        # must not delete or replace it to make room for a link.
        result, _ = self.run_launcher(
            "launch",
            global_session_entries=True,
            preset_isolated_projects=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        projects = self.isolated / "projects"
        self.assertFalse(projects.is_symlink())
        self.assertIn("plane-local", (projects / "local" / "session.jsonl").read_text())
        self.assertIn("NOT INHERITED", result.stdout)

    def test_a_skipped_entry_says_inheritance_is_off_and_names_the_remedy(self) -> None:
        # The defect: on the operator's host every entry already held pre-feature data, so
        # inheritance was a permanent no-op, and the old wording ("isolated copy already has its
        # own data") read as a benign implementation note rather than "the feature is off". The
        # message must now be unmistakable AND name the fix in the same breath, because a true
        # statement nobody registers as important is the failure being corrected.
        result, _ = self.run_launcher(
            "launch",
            global_session_entries=True,
            preset_isolated_projects=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("projects NOT INHERITED", result.stdout)
        self.assertIn("inheritance is OFF", result.stdout)
        self.assertIn("ccodex session adopt", result.stdout)
        self.assertIn("never deletes", result.stdout)
        # The old softening wording is gone, not merely supplemented.
        self.assertNotIn("already has its own data", result.stdout)

    def test_launch_never_migrates_plane_data_by_itself(self) -> None:
        # The remedy must be an operation the operator names. A launch that quietly moved their
        # data aside to deliver inheritance would be the opposite failure.
        result, _ = self.run_launcher(
            "launch",
            global_session_entries=True,
            preset_isolated_projects=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plane-local", (self.isolated / "projects" / "local" / "session.jsonl").read_text())
        self.assertFalse(list(self.isolated.glob("pre-inheritance-backup-*")))

    def test_status_surfaces_how_many_entries_are_actually_shared(self) -> None:
        # A plane whose inheritance never took effect looks identical to one where it did, until
        # the operator notices their history is missing. The count makes it visible without
        # running a special command.
        result, _ = self.run_launcher(
            "status", global_session_entries=True, preset_isolated_projects=True
        )

        self.assertIn("session inheritance:", result.stdout)
        self.assertIn("entries shared", result.stdout)
        self.assertIn("projects", result.stdout)
        self.assertIn("NOT INHERITED", result.stdout)

    # --- session status / adopt: the explicit, reviewable remedy ---------------------------

    def test_session_status_reports_each_entry_and_changes_nothing(self) -> None:
        launched, _ = self.run_launcher(
            "launch", global_session_entries=True, preset_isolated_projects=True
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)
        before = sorted(path.name for path in self.isolated.iterdir())

        result = subprocess.run(
            [BASH, str(SCRIPT), "session", "status"],
            text=True, capture_output=True, check=False, env={**self.launch_env},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("session inheritance:", result.stdout)
        # history.jsonl linked on the first launch; projects blocked by its own data.
        self.assertIn("history.jsonl    SHARED", result.stdout)
        self.assertIn("projects         NOT INHERITED", result.stdout)
        # Read-only: no entry appeared, disappeared, or was migrated.
        self.assertEqual(before, sorted(path.name for path in self.isolated.iterdir()))
        self.assertFalse(list(self.isolated.glob("pre-inheritance-backup-*")))

    def test_session_adopt_without_the_flag_moves_nothing(self) -> None:
        launched, _ = self.run_launcher(
            "launch", global_session_entries=True, preset_isolated_projects=True
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)

        result = subprocess.run(
            [BASH, str(SCRIPT), "session", "adopt"],
            text=True, capture_output=True, check=False, env={**self.launch_env},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PLAN ONLY", result.stdout)
        self.assertIn("would MOVE", result.stdout)
        self.assertIn("NOTHING WAS MOVED", result.stdout)
        # The plan names the exact source and destination before anything is authorized.
        self.assertIn(str(self.isolated / "projects"), result.stdout)
        self.assertIn("pre-inheritance-backup-", result.stdout)
        self.assertFalse((self.isolated / "projects").is_symlink())
        self.assertFalse(list(self.isolated.glob("pre-inheritance-backup-*")))
        self.assertIn("plane-local", (self.isolated / "projects" / "local" / "session.jsonl").read_text())

    def test_session_adopt_migrate_backs_up_then_links_and_deletes_nothing(self) -> None:
        launched, _ = self.run_launcher(
            "launch", global_session_entries=True, preset_isolated_projects=True
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)

        result = subprocess.run(
            [BASH, str(SCRIPT), "session", "adopt", "--migrate"],
            text=True, capture_output=True, check=False, env={**self.launch_env},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        projects = self.isolated / "projects"
        self.assertTrue(projects.is_symlink())
        self.assertEqual(projects.resolve(), (self.global_claude / "projects").resolve())
        # The plane's own data was MOVED, never deleted, and the path is printed.
        backups = list(self.isolated.glob("pre-inheritance-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn(
            "plane-local",
            (backups[0] / "projects" / "local" / "session.jsonl").read_text(),
        )
        self.assertIn(str(backups[0]), result.stdout)
        # The consequence is stated rather than left to be discovered.
        self.assertIn("no longer appear", result.stdout)

    def test_session_adopt_refuses_when_the_global_source_is_missing(self) -> None:
        # Moving the plane's only copy aside with nothing to link to would hide the operator's
        # data to deliver nothing, so this is a refusal rather than a skip.
        launched, _ = self.run_launcher("launch", preset_isolated_projects=True)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        shutil.rmtree(self.global_claude, ignore_errors=True)

        result = subprocess.run(
            [BASH, str(SCRIPT), "session", "adopt", "--migrate"],
            text=True, capture_output=True, check=False, env={**self.launch_env},
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("plane-local", (self.isolated / "projects" / "local" / "session.jsonl").read_text())
        self.assertFalse(list(self.isolated.glob("pre-inheritance-backup-*")))

    def test_session_adopt_refuses_a_named_entry_with_no_global_counterpart(self) -> None:
        launched, _ = self.run_launcher(
            "launch", global_session_entries=True, preset_isolated_projects=True
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)
        # todos/ exists in this plane but not in the fake global install.
        (self.isolated / "todos").mkdir(parents=True, exist_ok=True)
        (self.isolated / "todos" / "t.json").write_text("plane-todo\n")

        result = subprocess.run(
            [BASH, str(SCRIPT), "session", "adopt", "--migrate", "todos"],
            text=True, capture_output=True, check=False, env={**self.launch_env},
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("REFUSED", result.stderr)
        self.assertEqual((self.isolated / "todos" / "t.json").read_text(), "plane-todo\n")
        # A named entry restricts the operation: the unrelated blocked entry is untouched.
        self.assertFalse((self.isolated / "projects").is_symlink())

    def test_session_routes_need_no_gateway_and_no_ocx(self) -> None:
        # "Why is my history missing" must be answerable exactly when the gateway is down.
        launched, _ = self.run_launcher("launch", global_session_entries=True)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        without_mise = {**self.launch_env, "PATH": "/usr/bin:/bin"}

        for arguments in (["session", "status"], ["session", "adopt"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [BASH, str(SCRIPT), *arguments],
                    text=True, capture_output=True, check=False, env=without_mise,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("mise is required", result.stderr)

    def test_unknown_session_verb_and_flag_exit_usage(self) -> None:
        for arguments in (
            ("session", "bogus"),
            ("session", "adopt", "--force"),
            ("session", "status", "extra"),
            ("session",),
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher(*arguments, global_session_entries=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(log.exists(), "a usage error must invoke no ocx route")

    # --- help is not a side-effecting operation ------------------------------------------
    #
    # The defect: `launch --help` ran the whole launch preparation -- mounted session
    # inheritance, constructed settings.json in the isolated dir, and against a healthy gateway
    # would have launched -- before handing --help to Claude Code. These assert on OUTPUT, never
    # on exit status alone: with a stubbed `claude` that exits 0, an exit code cannot distinguish
    # "printed usage" from "launched Claude Code, which then exited cleanly".

    SIDE_EFFECT_MARKER = "preparing gateway-routed Claude Code"

    def test_verb_level_help_prints_usage_and_prepares_nothing(self) -> None:
        for arguments in (
            ["launch", "--help"],
            ["launch", "-h"],
            ["launch", "help"],
            ["launch-ultracode", "--help"],
            ["launch-ultracode", "-h"],
            ["status", "--help"],
            ["restart", "--help"],
            ["session", "--help"],
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
                self.assertFalse((self.isolated / "settings.json").exists())
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
