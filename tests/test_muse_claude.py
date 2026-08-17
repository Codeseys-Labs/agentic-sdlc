from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "muse-claude.sh"
BASH = shutil.which("bash")

# Every test below runs against a stub `curl` and a placeholder key. No test requires the real
# Muse Spark credential, and no test performs a network call: the launcher's contract is its
# refusal and validation logic, which is exactly what a stub can exercise deterministically.
PLACEHOLDER_KEY = "muse-test-placeholder-not-a-real-credential"


def wire(payload: object) -> str:
    """Serialize the way the endpoint actually does: no whitespace after separators.

    The launcher matches quoted JSON fragments (`"id":"muse-spark-1.2"`) against raw response
    bytes, so a fixture with Python's default `", "` spacing would not represent the real wire
    format and would exercise a case the endpoint never produces.
    """
    return json.dumps(payload, separators=(",", ":"))


CATALOG = wire(
    {
        "object": "list",
        "data": [
            {"id": "muse-spark-1.2-contributor", "object": "model"},
            {"id": "muse-spark-1.2", "object": "model"},
            {"id": "muse-spark-1.1", "object": "model"},
        ],
    }
)
COMPLETION = wire(
    {
        "content": [{"data": "opaque", "type": "redacted_thinking"}, {"text": "ready", "type": "text"}],
        "model": "muse-spark-1.2",
        "stop_reason": "end_turn",
    }
)
# The documented hazard: HTTP 200 whose content array carries no text block, because reasoning
# tokens consumed the whole output budget.
EMPTY_COMPLETION = wire({"content": [], "model": "muse-spark-1.2", "stop_reason": "max_tokens"})


@unittest.skipUnless(BASH, "bash is required")
class MuseClaudeTests(unittest.TestCase):
    def run_launcher(
        self,
        *arguments: str,
        catalog_status: str = "200",
        catalog_body: str = CATALOG,
        completion_status: str = "200",
        completion_body: str = COMPLETION,
        key: str | None = PLACEHOLDER_KEY,
        key_file: str | None = None,
        extra_env: dict[str, str] | None = None,
        with_claude: bool = True,
        global_settings: object | None = None,
        global_session_entries: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        # Fake global ~/.claude for selective session inheritance (ADR-0010). The real
        # operator config dir is never read or written by any test.
        self.global_claude = root / "home" / ".claude"
        self.isolated = root / "state" / "agentic-sdlc" / "muse-claude"
        if global_settings is not None:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "settings.json").write_text(json.dumps(global_settings))
        if global_session_entries:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "history.jsonl").write_text('{"display":"real prompt"}\n')
            (self.global_claude / "projects" / "demo").mkdir(parents=True, exist_ok=True)
            (self.global_claude / "projects" / "demo" / "session.jsonl").write_text("{}\n")
        curl_log = root / "curl.log"
        claude_log = root / "claude.log"

        # The stub log variables are deliberately NOT named CLAUDE_*/ANTHROPIC_*/AWS_*: the
        # launcher scrubs those whole namespaces out of the child environment, which would take a
        # stub's own log path with it. test_child_environment_is_scrubbed_and_repointed and
        # test_bedrock_and_unprefixed_hazards_never_reach_the_child assert that scrub.

        # Stub curl: records the request it was given (including whether the credential arrived
        # in argv, which is what the ps-visibility assertion reads) and replays a canned body.
        curl = bin_dir / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            'printf "ARGV:%s\\n" "$*" >> "$CURL_LOG"\n'
            'config=$(cat)\n'
            'printf "STDIN:%s\\n" "$config" >> "$CURL_LOG"\n'
            'for a in "$@"; do\n'
            '  case "$a" in *"/v1/models") printf "%s\\n%s" "$CATALOG_BODY" "$CATALOG_STATUS"; exit 0 ;; esac\n'
            'done\n'
            'printf "%s\\n%s" "$COMPLETION_BODY" "$COMPLETION_STATUS"\n'
        )
        curl.chmod(0o755)

        if with_claude:
            claude = bin_dir / "claude"
            # Records argv plus every variable the scrub policy governs, so a test can assert what
            # survived the scrub and what was re-exported afterwards. The recorded set is the whole
            # of ADR-0010 Amendment A -- the ANTHROPIC/CLAUDE/AWS prefixes plus the three
            # denied-by-name unprefixed hazards -- because a name the stub does not record cannot
            # be asserted absent from the child.
            claude.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$MUSE_TEST_CLAUDE_LOG"\n'
                'env | grep -E "^(ANTHROPIC|CLAUDE|AWS|NODE_TLS_REJECT_UNAUTHORIZED'
                '|FALLBACK_FOR_ALL_PRIMARY_MODELS|API_TIMEOUT_MS)"'
                ' | sort >> "$MUSE_TEST_CLAUDE_LOG"\n'
                "exit 0\n"
            )
            claude.chmod(0o755)

        env = {
            "HOME": str(root / "home"),
            "XDG_STATE_HOME": str(root / "state"),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "CURL_LOG": str(curl_log),
            "MUSE_TEST_CLAUDE_LOG": str(claude_log),
            "CATALOG_BODY": catalog_body,
            "CATALOG_STATUS": catalog_status,
            "COMPLETION_BODY": completion_body,
            "COMPLETION_STATUS": completion_status,
        }
        if key is not None:
            env["MODEL_API_KEY"] = key
        if key_file is not None:
            env["MUSE_API_KEY_FILE"] = key_file
        if extra_env:
            env.update(extra_env)

        result = subprocess.run(
            [BASH, str(SCRIPT), *arguments],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        return result, curl_log, claude_log

    # --- credential handling ---------------------------------------------------------------

    def test_credential_never_appears_in_curl_argv(self) -> None:
        result, curl_log, _ = self.run_launcher("probe")

        self.assertEqual(result.returncode, 0, result.stderr)
        recorded = curl_log.read_text()
        argv_lines = [line for line in recorded.splitlines() if line.startswith("ARGV:")]
        self.assertTrue(argv_lines)
        for line in argv_lines:
            self.assertNotIn(PLACEHOLDER_KEY, line)
        # It must still have been delivered, via the config file on stdin.
        self.assertIn(f"Authorization: Bearer {PLACEHOLDER_KEY}", recorded)

    def test_credential_value_is_never_printed(self) -> None:
        for arguments in (("probe",), ("status",)):
            with self.subTest(arguments=arguments):
                result, _, _ = self.run_launcher(*arguments)
                self.assertNotIn(PLACEHOLDER_KEY, result.stdout + result.stderr)

    def test_credential_on_command_line_is_refused(self) -> None:
        for argument in ("--api-key=X", "--api-key", "--auth-token=X", "MODEL_API_KEY=X"):
            with self.subTest(argument=argument):
                result, curl_log, claude_log = self.run_launcher("launch", argument)
                self.assertEqual(result.returncode, 3)
                self.assertIn("REFUSED", result.stderr)
                self.assertFalse(curl_log.exists())
                self.assertFalse(claude_log.exists())

    def test_missing_credential_fails_before_any_request(self) -> None:
        result, curl_log, claude_log = self.run_launcher("probe", key=None)

        self.assertEqual(result.returncode, 1)
        self.assertIn("no Muse Spark credential found", result.stderr)
        self.assertFalse(curl_log.exists())
        self.assertFalse(claude_log.exists())

    def test_credential_file_inside_the_repository_is_refused(self) -> None:
        in_repo = SCRIPT.parents[1] / "tests" / "fixtures"
        result, curl_log, _ = self.run_launcher(
            "probe", key=None, key_file=str(in_repo / "would-be-key")
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to read a credential from inside the repository", result.stderr)
        self.assertFalse(curl_log.exists())

    def test_credential_file_outside_the_repository_is_read_and_trimmed(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        key_file = Path(temporary.name) / "api-key"
        key_file.write_text(f"  {PLACEHOLDER_KEY}\n")

        result, curl_log, _ = self.run_launcher("probe", key=None, key_file=str(key_file))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"Authorization: Bearer {PLACEHOLDER_KEY}\"", curl_log.read_text())
        self.assertIn(f"file:{key_file}", result.stdout)

    def test_empty_credential_file_is_rejected(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        key_file = Path(temporary.name) / "api-key"
        key_file.write_text("\n")

        result, curl_log, _ = self.run_launcher("probe", key=None, key_file=str(key_file))

        self.assertEqual(result.returncode, 1)
        self.assertIn("empty", result.stderr)
        self.assertFalse(curl_log.exists())

    # --- subscription-OAuth boundary -------------------------------------------------------

    def test_subscription_token_refuses_before_any_request(self) -> None:
        result, curl_log, claude_log = self.run_launcher(
            "launch",
            extra_env={"ANTHROPIC_AUTH_TOKEN": "sk-ant-oat-synthetic-fixture-not-a-credential"},
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("docs/adr/0003", result.stderr)
        self.assertFalse(curl_log.exists())
        self.assertFalse(claude_log.exists())

    def test_subscription_marker_in_isolated_state_refuses(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        state = Path(temporary.name)
        config_dir = state / "agentic-sdlc" / "muse-claude"
        config_dir.mkdir(parents=True)
        (config_dir / ".credentials.json").write_text(wire({"claudeAiOauth": {}}))

        result, curl_log, claude_log = self.run_launcher(
            "launch", extra_env={"XDG_STATE_HOME": str(state)}
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("subscription OAuth marker", result.stderr)
        self.assertFalse(curl_log.exists())
        self.assertFalse(claude_log.exists())

    def test_developer_api_key_is_scrubbed_not_refused(self) -> None:
        # sk-ant-api* is a different credential class than the subscription OAuth token
        # ADR-0003 forbids, so it must be scrubbed out of the child rather than refused.
        result, _, claude_log = self.run_launcher(
            "launch", extra_env={"ANTHROPIC_API_KEY": "sk-ant-api-synthetic-fixture"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(claude_log.exists())

    # --- fail-closed route verification ----------------------------------------------------

    def test_catalog_401_names_both_causes_and_does_not_launch(self) -> None:
        result, _, claude_log = self.run_launcher(
            "launch", catalog_status="401", catalog_body='{"error":{"message":"Unauthorized"}}'
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL-CLOSED", result.stderr)
        # The whole point of this branch: a wrong base URL and a bad key are indistinguishable
        # at 401, so the message must name both rather than blaming the credential.
        self.assertIn("base URL is wrong", result.stderr)
        self.assertFalse(claude_log.exists())

    def test_model_absent_from_catalog_does_not_launch(self) -> None:
        thin_catalog = wire({"data": [{"id": "muse-spark-1.1"}]})
        result, _, claude_log = self.run_launcher("launch", catalog_body=thin_catalog)

        self.assertEqual(result.returncode, 1)
        self.assertIn("NOT in the served catalog", result.stderr)
        self.assertFalse(claude_log.exists())

    def test_catalog_membership_is_not_matched_by_substring(self) -> None:
        # muse-spark-1.2 must not be considered present merely because the catalog lists
        # muse-spark-1.2-contributor, which contains it as a prefix.
        catalog = wire({"data": [{"id": "muse-spark-1.2-contributor"}, {"id": "muse-spark-1.1"}]})
        result, _, claude_log = self.run_launcher("launch", catalog_body=catalog)

        self.assertEqual(result.returncode, 1)
        self.assertIn("NOT in the served catalog", result.stderr)
        self.assertFalse(claude_log.exists())

    def test_empty_200_completion_fails_closed(self) -> None:
        result, _, claude_log = self.run_launcher("launch", completion_body=EMPTY_COMPLETION)

        self.assertEqual(result.returncode, 1)
        self.assertIn("EMPTY output text", result.stderr)
        self.assertFalse(claude_log.exists())

    def test_completion_reporting_a_different_model_fails_closed(self) -> None:
        mismatched = wire(
            {"content": [{"text": "ready", "type": "text"}], "model": "muse-spark-1.1"}
        )
        result, _, claude_log = self.run_launcher("launch", completion_body=mismatched)

        self.assertEqual(result.returncode, 1)
        self.assertIn("different model than requested", result.stderr)
        self.assertFalse(claude_log.exists())

    def test_completion_non_200_fails_closed(self) -> None:
        result, _, claude_log = self.run_launcher("launch", completion_status="500")

        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL-CLOSED", result.stderr)
        self.assertFalse(claude_log.exists())

    # --- launch shape ----------------------------------------------------------------------

    def test_launch_verifies_before_exec_and_forwards_arguments(self) -> None:
        result, curl_log, claude_log = self.run_launcher("launch", "--settings", '{"a":1}', "two words")

        self.assertEqual(result.returncode, 0, result.stderr)
        # Both checks ran before claude was exec'd.
        recorded = curl_log.read_text()
        self.assertIn("/v1/models", recorded)
        self.assertIn("/v1/messages", recorded)
        self.assertIn('--settings {"a":1} two words', claude_log.read_text())

    def test_child_environment_is_scrubbed_and_repointed(self) -> None:
        # A parent-session routing flag or per-tier model slot leaking into the child would send
        # it somewhere other than Meta, so the scrub is a prefix scrub and the slots this route
        # needs are re-exported after it.
        result, _, claude_log = self.run_launcher(
            "launch",
            extra_env={
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "ANTHROPIC_MODEL": "claude-opus-4-8",
                "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        inherited = claude_log.read_text()
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", inherited)
        self.assertNotIn("api.anthropic.com", inherited)
        self.assertNotIn("claude-opus-4-8", inherited)
        self.assertIn("ANTHROPIC_BASE_URL=https://api.meta.ai", inherited)
        self.assertIn("ANTHROPIC_MODEL=muse-spark-1.2", inherited)
        self.assertIn("ANTHROPIC_SMALL_FAST_MODEL=muse-spark-1.1", inherited)
        # The credential reaches the child through the Anthropic auth slot and nowhere else.
        self.assertIn(f"ANTHROPIC_AUTH_TOKEN={PLACEHOLDER_KEY}", inherited)

    def test_bedrock_and_unprefixed_hazards_never_reach_the_child(self) -> None:
        # ADR-0010 Amendment A, which exists because an exported AWS_BEARER_TOKEN_BEDROCK reached
        # the child intact: AWS_* is denied by prefix and these three unprefixed names by name. The
        # constructed settings.json cannot cover this half of the boundary -- Claude Code resolves
        # the shell environment ABOVE settings `env` -- so the scrub is the only control here.
        credential_shaped = {
            "AWS_BEARER_TOKEN_BEDROCK": "planted-bedrock-bearer-not-a-credential",
            # Deliberately NOT an AKIA-shaped value: a realistic-looking fixture would trip the
            # repository's own tracked-text secrets scan, and the scrub does not read the value.
            "AWS_ACCESS_KEY_ID": "planted-access-key-id-not-a-credential",
            "AWS_SECRET_ACCESS_KEY": "planted-bedrock-secret-not-a-credential",
        }
        planted = {
            **credential_shaped,
            "AWS_REGION": "us-east-1",
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
            "FALLBACK_FOR_ALL_PRIMARY_MODELS": "claude-opus-4-8",
            "API_TIMEOUT_MS": "600000",
        }
        result, _, claude_log = self.run_launcher("launch", extra_env=planted)

        self.assertEqual(result.returncode, 0, result.stderr)
        inherited = claude_log.read_text()
        # Positive control first: the stub really does record the child's environment, so the
        # absence assertions below cannot pass merely because nothing was recorded.
        self.assertIn("ANTHROPIC_BASE_URL=https://api.meta.ai", inherited)
        for name in planted:
            with self.subTest(variable=name):
                self.assertNotIn(name, inherited)
        # Values as well as names, for the ones that are credentials. The short values above
        # (a region, `0`, a timeout) are not asserted: they occur incidentally in a temp path.
        for value in credential_shaped.values():
            with self.subTest(value=value):
                self.assertNotIn(value, inherited)
        self.assertNotIn("planted-", result.stdout + result.stderr)

    def test_launch_does_not_print_forwarded_secret(self) -> None:
        secret = "MUSE_TEST_FORWARDED_SECRET"
        result, _, _ = self.run_launcher("launch", "--settings", f'{{"token":"{secret}"}}')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_base_url_has_no_v1_suffix_by_default(self) -> None:
        # Claude Code appends /v1/messages itself, so the configured base must not already end
        # in /v1 -- that produces /v1/v1/messages, which answers 401 and reads as a bad key.
        result, curl_log, _ = self.run_launcher("probe")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://api.meta.ai/v1/models", curl_log.read_text())
        self.assertNotIn("/v1/v1/", curl_log.read_text())

    def test_probe_never_launches_claude(self) -> None:
        result, curl_log, claude_log = self.run_launcher("probe")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(curl_log.exists())
        self.assertFalse(claude_log.exists())

    def test_probe_states_the_route_is_tier_unproven(self) -> None:
        result, _, _ = self.run_launcher("probe")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TIER-UNPROVEN", result.stdout)
        self.assertIn("not authorization", result.stdout)

    def test_status_reports_credential_source_without_value(self) -> None:
        result, _, claude_log = self.run_launcher("status")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("environment:MODEL_API_KEY", result.stdout)
        self.assertNotIn(PLACEHOLDER_KEY, result.stdout)
        self.assertFalse(claude_log.exists())

    def test_missing_claude_cli_fails_without_launching(self) -> None:
        result, _, claude_log = self.run_launcher("launch", with_claude=False)

        self.assertEqual(result.returncode, 1)
        self.assertIn("not on PATH", result.stderr)
        self.assertFalse(claude_log.exists())

    def test_usage_and_unknown_subcommand_exit_codes(self) -> None:
        result, _, _ = self.run_launcher()
        self.assertEqual(result.returncode, 2)

        result, _, claude_log = self.run_launcher("nonsense")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(claude_log.exists())

    # --- fallback framing ---------------------------------------------------------------
    #
    # ADR-0007 makes the gateway the primary path. A verdict-reporting subcommand that did not
    # say so would leave an operator believing this is THE route, which is the mistake the ADR
    # revision exists to correct -- so it is asserted rather than left to the header comment.

    def test_probe_and_status_name_the_gateway_as_the_primary_path(self) -> None:
        for subcommand in ("probe", "status"):
            with self.subTest(subcommand=subcommand):
                result, _, _ = self.run_launcher(subcommand)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("FALLBACK", result.stdout)
                self.assertIn("opencodex-claude.sh launch", result.stdout)
                self.assertIn("muse/muse-spark-1.2", result.stdout)
                # The reason, not merely the label: the identity ceiling is why it is second.
                # Matched on unwrapped text, since the notice is hard-wrapped prose.
                unwrapped = " ".join(result.stdout.split())
                self.assertIn("ONLY identity channel and it ECHOES the request", unwrapped)
                self.assertIn("no attribution log", unwrapped)

    def test_usage_names_the_gateway_as_the_primary_path(self) -> None:
        result, _, _ = self.run_launcher("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FALLBACK", result.stdout)
        self.assertIn("opencodex-claude.sh launch", result.stdout)

    # --- selective session inheritance (ADR-0010) -----------------------------------------
    #
    # This route shares the ocx launcher's helper, so the boundary cannot drift between them.
    # These tests assert the same two halves HERE, because a shared helper is only as good as
    # the call site: this launcher re-exports ANTHROPIC_* slots after the scrub, so a copied
    # global `env` block would silently re-point it away from Meta.

    CREDENTIAL_BEARING_GLOBAL_SETTINGS = {
        "env": {
            "AWS_BEARER_TOKEN_BEDROCK": "planted-bedrock-bearer-value",
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "ANTHROPIC_BASE_URL": "https://planted.bedrock.example",
        },
        "statusLine": {"type": "command", "command": "/global/statusline-command.sh"},
        "apiKeyHelper": "/global/print-my-key.sh",
    }

    def test_statusline_is_inherited_without_the_credential(self) -> None:
        result, _, _ = self.run_launcher(
            "launch", global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        raw = (self.isolated / "settings.json").read_text()
        document = json.loads(raw)
        self.assertEqual(document["statusLine"]["command"], "/global/statusline-command.sh")
        self.assertNotIn("planted-bedrock-bearer-value", raw)
        self.assertNotIn("env", document)
        self.assertNotIn("apiKeyHelper", document)
        self.assertNotIn("planted-bedrock-bearer-value", result.stdout + result.stderr)

    def test_inherited_settings_never_repoint_the_route_away_from_meta(self) -> None:
        # The concrete hazard for THIS launcher: a copied global env block carries
        # ANTHROPIC_BASE_URL and CLAUDE_CODE_USE_BEDROCK, which would send the process to
        # Bedrock while the probe reported Meta as healthy.
        result, _, claude_log = self.run_launcher(
            "launch", global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        recorded = claude_log.read_text()
        self.assertIn("ANTHROPIC_BASE_URL=https://api.meta.ai", recorded)
        self.assertNotIn("planted.bedrock.example", recorded)
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", recorded)

    def test_inert_session_entries_are_shared_by_symlink(self) -> None:
        result, _, _ = self.run_launcher("launch", global_session_entries=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in ("history.jsonl", "projects"):
            with self.subTest(entry=entry):
                target = self.isolated / entry
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.resolve(), (self.global_claude / entry).resolve())
        self.assertIn("real prompt", (self.isolated / "history.jsonl").read_text())

    def test_credential_stores_are_never_shared(self) -> None:
        result, _, _ = self.run_launcher(
            "launch",
            global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS,
            global_session_entries=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in (".credentials.json", "sessions", "session-env", "plugins", "agents"):
            with self.subTest(entry=entry):
                self.assertFalse((self.isolated / entry).is_symlink())

    def test_nothing_is_inherited_when_the_route_fails_closed(self) -> None:
        # Inheritance runs after route verification, so an unreachable endpoint links nothing.
        result, _, _ = self.run_launcher(
            "launch",
            catalog_status="401",
            catalog_body="{}",
            global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS,
            global_session_entries=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.isolated / "settings.json").exists())
        self.assertFalse((self.isolated / "history.jsonl").is_symlink())

    def test_subscription_refusal_links_nothing(self) -> None:
        result, _, _ = self.run_launcher(
            "launch",
            extra_env={"ANTHROPIC_AUTH_TOKEN": "sk-ant-oat-planted"},
            global_settings=self.CREDENTIAL_BEARING_GLOBAL_SETTINGS,
            global_session_entries=True,
        )

        self.assertEqual(result.returncode, 3)
        self.assertFalse((self.isolated / "settings.json").exists())
        self.assertFalse((self.isolated / "history.jsonl").is_symlink())


if __name__ == "__main__":
    unittest.main()
