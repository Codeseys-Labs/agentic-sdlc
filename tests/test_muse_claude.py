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

    # --- ADR-0010 Amendment A: CLAUDE_* is denied by default and ALLOWED BY NAME -----------
    #
    # The deny half was shipped; the allow half was not, so a deliberately-set
    # CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC was swept with everything else -- and because that
    # flag is SET-TO-ACTIVATE, dropping a set flag silently RE-ENABLES the traffic in the launched
    # plane. These tests assert both halves in the same child, because the failure mode of
    # allow-by-name is allowing too MUCH: a passing allow test next to a missing deny test is
    # exactly how a credential crosses the boundary.

    def assert_channel_records(self, claude_log: Path, planted: dict[str, str]) -> None:
        """Positive control for the observation channel used by the tests below.

        A previous version of this stub recorded only ANTHROPIC_*/CLAUDE_*-prefixed names, so a
        planted AWS_BEARER_TOKEN_BEDROCK passed its absence assertion VACUOUSLY -- the token was
        in the child and the test could not see it. So before asserting that a name is absent
        from a recorded child environment, prove the recorder would have shown it: run the same
        stub directly with the same planted names and require every one of them, with its value,
        in the log it writes.
        """
        stub = claude_log.parent / "bin" / "claude"
        control_log = claude_log.parent / "channel-control.log"
        subprocess.run(
            [str(stub)],
            env={"PATH": "/usr/bin:/bin", "MUSE_TEST_CLAUDE_LOG": str(control_log), **planted},
            check=True,
        )
        recorded = control_log.read_text()
        for name, value in planted.items():
            with self.subTest(channel=name):
                self.assertIn(
                    f"{name}={value}",
                    recorded,
                    f"the observation channel does not carry {name}; an absence assertion "
                    "about it would pass vacuously",
                )

    def test_named_claude_flags_survive_the_scrub_with_their_exact_values(self) -> None:
        allowed = {
            # The privacy flag Amendment A names explicitly. Set-to-activate: dropping it is a
            # privacy regression the operator never asked for.
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            # The accessibility and compaction classes Amendment A names by category.
            "CLAUDE_CODE_ACCESSIBILITY": "1",
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "123456",
            # An operator percentage must still beat the opinionated 85 default (ADR-0012).
            "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "40",
        }
        result, _, claude_log = self.run_launcher("launch", extra_env=dict(allowed))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_channel_records(claude_log, allowed)
        inherited = claude_log.read_text()
        for name, value in allowed.items():
            with self.subTest(variable=name):
                self.assertIn(f"{name}={value}", inherited)

    def test_the_opinionated_percentage_still_applies_when_the_operator_set_none(self) -> None:
        result, _, claude_log = self.run_launcher("launch")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85", claude_log.read_text())

    def test_allow_by_name_still_denies_every_other_class_in_the_same_child(self) -> None:
        denied = {
            # Wrong namespace: ANTHROPIC_* is denied by prefix with no exceptions.
            "ANTHROPIC_API_KEY": "sk-ant-api-planted-not-a-credential",
            # The finding Amendment A exists for: an exported Bedrock bearer token.
            "AWS_BEARER_TOKEN_BEDROCK": "planted-bedrock-bearer-not-a-credential",
            # Unprefixed, denied by name.
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
            # CLAUDE_*-prefixed but NOT on the allowlist: an unrecognized name is dropped rather
            # than guessed at, which is the whole reason the allow half is an enumeration.
            "CLAUDE_CODE_UNRECOGNIZED_FUTURE_FLAG": "1",
        }
        allowed = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
        result, _, claude_log = self.run_launcher(
            "launch", extra_env={**denied, **allowed}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_channel_records(claude_log, {**denied, **allowed})
        inherited = claude_log.read_text()
        # The allow half worked in this exact child, so the denials below are not passing merely
        # because the whole namespace was swept.
        self.assertIn("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1", inherited)
        for name, value in denied.items():
            with self.subTest(variable=name):
                self.assertNotIn(name, inherited)
                # Values are asserted only where they are distinguishable. A `0` or a `1` occurs
                # incidentally in a temp path and in the surviving flags, so asserting those
                # would be a coin flip rather than a control.
                if len(value) > 8:
                    self.assertNotIn(value, inherited)
        self.assertNotIn("planted-", result.stdout + result.stderr)

    def test_a_missing_policy_helper_fails_closed_instead_of_launching_unscrubbed(self) -> None:
        # The scrub moved out of this script and into the shared helper, which introduces a way for
        # it to be ABSENT. Session inheritance is fail-soft about exactly that, and the scrub must
        # not be: a launch without it hands the parent's ANTHROPIC_*/AWS_* environment to the child.
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "scripts").mkdir()
        (root / "assets" / "claude").mkdir(parents=True)
        shutil.copy(SCRIPT, root / "scripts" / "muse-claude.sh")
        asset = SCRIPT.parents[1] / "assets" / "claude" / "session-inheritance.sh"
        environment = {
            "HOME": str(root / "home"),
            "XDG_STATE_HOME": str(root / "state"),
            "PATH": "/usr/bin:/bin",
            "MODEL_API_KEY": PLACEHOLDER_KEY,
        }

        def launch() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [BASH, str(root / "scripts" / "muse-claude.sh"), "launch"],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
            )

        without_helper = launch()
        self.assertEqual(without_helper.returncode, 1)
        self.assertIn("FAIL-CLOSED", without_helper.stderr)
        self.assertIn("session-inheritance.sh", without_helper.stderr)
        self.assertIn("Claude Code was NOT launched", without_helper.stderr)

        # Positive control: with the helper restored, the SAME tree gets past the scrub and stops
        # later for an unrelated reason. Without this, the refusal above could be any failure of a
        # copied tree rather than the missing policy.
        shutil.copy(asset, root / "assets" / "claude" / "session-inheritance.sh")
        with_helper = launch()
        self.assertEqual(with_helper.returncode, 1)
        self.assertNotIn("FAIL-CLOSED", with_helper.stderr)
        self.assertIn("not on PATH", with_helper.stderr)

    def test_status_reports_the_environment_policy_by_class_and_never_a_value(self) -> None:
        planted = {
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_UNRECOGNIZED_FUTURE_FLAG": "1",
            "AWS_BEARER_TOKEN_BEDROCK": "planted-bedrock-bearer-not-a-credential",
        }
        result, _, _ = self.run_launcher("status", extra_env=planted)

        self.assertEqual(result.returncode, 0, result.stderr)
        report = result.stdout
        self.assertIn("environment policy", report)
        # Every planted name is classified, so the report is not silently blind to a class.
        for name in planted:
            with self.subTest(variable=name):
                self.assertIn(name, report)
        self.assertRegex(
            report, r"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC\s+INHERITED"
        )
        self.assertRegex(report, r"CLAUDE_CODE_UNRECOGNIZED_FUTURE_FLAG\s+DENIED")
        self.assertRegex(report, r"AWS_BEARER_TOKEN_BEDROCK\s+DENIED")
        # Names are reportable; values never are.
        self.assertNotIn("planted-bedrock-bearer-not-a-credential", result.stdout + result.stderr)


@unittest.skipUnless(BASH, "bash is required")
class SharedEnvironmentPolicyTests(unittest.TestCase):
    """The shared helper itself (assets/claude/session-inheritance.sh).

    The launcher tests above prove the policy at its one call site. These prove the properties
    that a call site cannot exercise: that the shipped allowlist passes its own admission check,
    that a widened or wrong-namespace list REFUSES instead of scrubbing, and that a value the
    operator controls cannot smuggle a second variable name through the capture-then-restore.
    """

    ASSET = Path(__file__).parents[1] / "assets" / "claude" / "session-inheritance.sh"

    def run_policy(
        self, body: str, env: dict[str, str] | None = None, source: bool = True
    ) -> subprocess.CompletedProcess[str]:
        script = "set -uo pipefail\n"
        if source:
            script += f'. "{self.ASSET}"\n'
        script += body
        return subprocess.run(
            [BASH, "-c", script],
            text=True,
            capture_output=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", **(env or {})},
            check=False,
        )

    def test_the_shipped_allowlist_passes_its_own_admission_check(self) -> None:
        # Positive control for every refusal test below: the real list is admissible, so those
        # nonzero exits are the guard working rather than the guard rejecting everything.
        result = self.run_policy('scrub_and_restore_claude_env; printf "SCRUBBED\\n"')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SCRUBBED", result.stdout)
        self.assertNotIn("REFUSED", result.stderr)

    def test_an_inadmissible_allowlist_entry_refuses_instead_of_scrubbing(self) -> None:
        # One careless future entry is how allow-by-name re-opens the boundary, so each of these
        # is refused by the list's own admission check rather than trusted to review.
        for entry in (
            "CLAUDE_CODE_USE_BEDROCK",  # a provider switch: routes the child off this plane
            "CLAUDE_CONFIG_DIR",  # a plane selector: would point the child at ~/.claude
            "CLAUDE_CODE_API_KEY_HELPER",  # credential-shaped
            "ANTHROPIC_API_KEY",  # wrong namespace; denied by prefix with no exceptions
            "AWS_BEARER_TOKEN_BEDROCK",  # the exact token the deny sweep exists for
            "CLAUDE_*",  # a pattern, not a name: no prefix-level allow is admissible
            "CLAUDE_CODE_DEFAULT_MODEL",  # a model pin
        ):
            with self.subTest(entry=entry):
                result = self.run_policy(
                    f"CLAUDE_INHERITED_ENV_VARS=({entry!r})\n"
                    'scrub_and_restore_claude_env && printf "SCRUBBED\\n"'
                )

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("SCRUBBED", result.stdout)
                self.assertIn("REFUSED", result.stderr)
                self.assertIn(entry, result.stderr)

    def test_an_empty_policy_list_refuses_rather_than_passing_vacuously(self) -> None:
        for mutation in (
            "CLAUDE_INHERITED_ENV_VARS=()",
            "CLAUDE_DENIED_ENV_VARS=()",
            "unset CLAUDE_INHERITED_ENV_VARS",
            "unset CLAUDE_DENIED_ENV_VARS",
        ):
            with self.subTest(mutation=mutation):
                result = self.run_policy(
                    f'{mutation}\nscrub_and_restore_claude_env && printf "SCRUBBED\\n"'
                )

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("SCRUBBED", result.stdout)
                self.assertIn("REFUSED", result.stderr)

    def test_a_newline_in_an_allowed_value_cannot_inject_a_second_name(self) -> None:
        # The capture-then-restore round-trips a value the OPERATOR controls. A `name=value`
        # line format would let a value containing a newline export a SECOND name of the
        # operator's choosing -- here a Bedrock bearer token, i.e. the exact boundary failure
        # this policy exists to prevent.
        injected = "AWS_BEARER_TOKEN_BEDROCK"
        value = f"1\n{injected}=planted-injected-not-a-credential"
        probe = (
            f'printf "INJECTED=[%s]\\n" "${{{injected}:-<unset>}}"\n'
            'printf "ALLOWED=[%s]\\n" "${CLAUDE_CODE_ACCESSIBILITY:-<unset>}"\n'
        )
        planted = {"CLAUDE_CODE_ACCESSIBILITY": value}

        # Positive control: the probe really does print that name's value when it is set, so the
        # `<unset>` assertion below is an observation rather than a blind spot.
        control = self.run_policy(
            probe, env={injected: "planted-control-not-a-credential"}, source=False
        )
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertIn("INJECTED=[planted-control-not-a-credential]", control.stdout)

        result = self.run_policy(f"scrub_and_restore_claude_env\n{probe}", env=planted)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INJECTED=[<unset>]", result.stdout)
        self.assertNotIn("planted-injected-not-a-credential", result.stdout.split("ALLOWED=")[0])
        # The allowed flag keeps its exact value, newline and all -- it is not truncated or split.
        self.assertIn(f"ALLOWED=[{value}]", result.stdout)


if __name__ == "__main__":
    unittest.main()
