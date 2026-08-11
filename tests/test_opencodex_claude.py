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
        global_settings_raw: str | None = None,
        global_settings_local: object | None = None,
        project_settings: object | None = None,
        project_settings_local: object | None = None,
        global_session_entries: bool = False,
        preset_isolated_settings: object | None = None,
        preset_isolated_projects: bool = False,
        parent_env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # RESOLVED ONCE, HERE, so the launcher's output and this harness's expectations cannot be
        # two spellings of one path. On macOS `$TMPDIR` is under `/var/folders/...` and `/var` is a
        # symlink to `/private/var`, so `mkdtemp()` hands back the UNRESOLVED spelling while the
        # launcher's own `$PWD` (bash sets it from getcwd, which is physical) is the resolved one.
        # `claude_settings_documents` builds its list from `$HOME` and `$PWD` and DEDUPLICATES it by
        # exact string, so an unresolved HOME against a resolved PWD makes one document count twice
        # and makes every `checked: <path>` line disagree with `self.project`. Resolving the root is
        # what makes that dedupe work off-Linux; sprinkling `.resolve()` at the assertions would
        # leave the launcher still emitting two spellings of the same file.
        root = Path(temporary.name).resolve()
        # A fake global ~/.claude, so selective session inheritance (ADR-0010) can be exercised
        # without ever reading or touching the real operator's config dir.
        self.home = root / "home"
        self.global_claude = self.home / ".claude"
        self.isolated = root / "state" / "agentic-sdlc" / "ocx-claude"
        if global_settings is not None:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "settings.json").write_text(json.dumps(global_settings))
        if global_settings_raw is not None:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "settings.json").write_text(global_settings_raw)
        if global_settings_local is not None:
            self.global_claude.mkdir(parents=True, exist_ok=True)
            (self.global_claude / "settings.local.json").write_text(json.dumps(global_settings_local))
        # The PROJECT-scoped documents, which Claude Code resolves against the directory the
        # launcher runs in. Every launch in this harness runs with cwd = self.project, so the
        # repository's own ./.claude is never what a test is really asserting about.
        self.project = root / "project"
        self.project.mkdir(parents=True, exist_ok=True)
        for name, payload in (
            ("settings.json", project_settings),
            ("settings.local.json", project_settings_local),
        ):
            if payload is not None:
                (self.project / ".claude").mkdir(parents=True, exist_ok=True)
                (self.project / ".claude" / name).write_text(json.dumps(payload))
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
        # ONE log under two names. The mise stub appends every `ocx` invocation to OCX_TRACE_LOG,
        # so the path handed to callers must BE that file. It was briefly a second, never-written
        # `calls.log`, which made every `log.read_text()` raise FileNotFoundError and every
        # `assertFalse(log.exists())` pass for the wrong reason. Assertions that mean "no MUTATION
        # ran" now check the trace CONTENT, because `require_ocx` legitimately runs `ocx --version`
        # first and that is not a mutation.
        self.ocx_trace_log = root / "ocx-trace.log"
        log = self.ocx_trace_log

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
            cwd=str(self.project),
            check=False,
        )
        return result, log

    # `require_ocx` runs `ocx --version`, and provider classification may run `ocx config show`,
    # before a refusal is reached. So an EMPTY trace is the wrong assertion for a refused route --
    # it is what made these checks pass vacuously while the trace file did not even exist.
    #
    # THE SECOND VACUITY, and why this is an ALLOWLIST now. The first fix for that was a BLACKLIST of
    # mutating route fragments, and it was itself substantially vacuous: the match is a
    # case-SENSITIVE substring test over lines of the harness stub's exact format
    # (`printf '<%s>' "$@"` over post-`--` argv, so every line begins `<ocx>`), and it therefore
    # MISSED `<ocx><logout><anthropic_key>` (`<login>` is not a substring of `<logout>`),
    # `<ocx><LoGiN><AnThRoPiC>`, `<ocx><setup>`, `<ocx><init>`, `<ocx><gui>`,
    # `<ocx><config><import>`, and `<ocx><provider><update|set-default>`. Five of the six
    # unbounded-route cases and two of the alias cases were asserting nothing at all.
    #
    # A blacklist of an unbounded surface cannot be completed -- every new upstream verb is a hole
    # opened by default -- so the assertion is inverted. The trace must contain ONLY lines from the
    # bounded set of genuinely read-only routes a refused path is allowed to reach. Anything else,
    # spelled any way, in any case, existing or future, fails.
    ADMITTED_READ_ONLY_OCX_ROUTES = (
        # require_ocx's own liveness probe, run before every route including a refused one.
        "<ocx><--version>",
        # provider classification, when a refusal needs to know what the provider is.
        "<ocx><config><show><--json>",
    )

    def assertOnlyReadOnlyOcxRoutes(self, log: Path, *also_admitted: str) -> None:
        """Fail unless every traced `ocx` invocation is an admitted read-only one.

        `also_admitted` widens the set for a test that legitimately reaches one more read-only
        route; it never narrows it, and a mutation is unreachable through it because the caller
        has to name the exact line.
        """
        admitted = set(self.ADMITTED_READ_ONLY_OCX_ROUTES) | set(also_admitted)
        trace = log.read_text() if log.exists() else ""
        unexpected = [line for line in trace.splitlines() if line.strip() and line not in admitted]
        self.assertEqual(
            unexpected, [], f"traced an ocx route outside the admitted set {sorted(admitted)}"
        )

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
        # `ocx health` is the identity-checked probe and is read-only, so this route legitimately
        # reaches one route the refusal paths do not. Widening it here rather than in the shared
        # tuple keeps every other caller's allowlist as tight as it was.
        self.assertOnlyReadOnlyOcxRoutes(log, "<ocx><health>")

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
    #
    # EVERY refusal below also asserts the TRACE, not only the exit code. These five checks
    # originally discarded it with `result, _ =`, which meant a regression that moved the refusal
    # BELOW ensure_gateway_up would still exit 3 and still pass -- while having started a gateway
    # the operator did not ask for, which is the specific thing `launch` orders its checks to avoid.
    # `assertOnlyReadOnlyOcxRoutes` pins that ordering: with the refusal first, the only traced
    # route is require_ocx's own `ocx --version`.

    def test_launch_refuses_a_provider_routing_variable_that_bypasses_the_gateway(self) -> None:
        for name in ("CLAUDE_CODE_USE_BEDROCK", "AWS_BEARER_TOKEN_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
            with self.subTest(name=name):
                result, log = self.run_launcher("launch", parent_env={name: "1"})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                # It must not claim to have routed anything it did not route.
                self.assertNotIn("routed at", result.stdout)
                # ... and it must not have started or contacted a gateway to find that out.
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_launch_refuses_a_bypassing_key_in_the_global_settings_document(self) -> None:
        # The channel an operator forgets: settings.json env is read on every launch and
        # survives a clean shell, so checking only the exported environment is not enough.
        result, log = self.run_launcher(
            "launch", global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}}
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CLAUDE_CODE_USE_BEDROCK", result.stderr)
        self.assertIn("settings.json", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_settings_credential_slots_are_judged_by_prefix_not_by_name(self) -> None:
        # An sk-ant-oat* token is the credential this route exists to carry, so WHERE it is stored
        # must not change the verdict: refusing it in settings.json while allowing the identical
        # token exported would reject a working own-login setup.
        accepted, accepted_log = self.run_launcher(
            "launch",
            global_settings={"env": {"ANTHROPIC_AUTH_TOKEN": "sk-ant-oat01-OCXTESTSENTINEL"}},
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        # The accepted half must actually LAUNCH; exit 0 alone cannot tell that from a no-op.
        self.assertIn("<ocx><claude>", accepted_log.read_text())

        refused, refused_log = self.run_launcher(
            "launch",
            global_settings={"env": {"ANTHROPIC_AUTH_TOKEN": "sk-ant-api03-OCXTESTSENTINEL"}},
        )
        self.assertEqual(refused.returncode, 3, refused.stderr)
        self.assertIn("credits", refused.stderr)
        self.assertNotIn("OCXTESTSENTINEL", refused.stdout + refused.stderr)
        self.assertOnlyReadOnlyOcxRoutes(refused_log)

    def test_an_uncheckable_settings_document_refuses_instead_of_passing_as_clean(self) -> None:
        # Fail-open was the bug: returning "nothing found" when the document could not be read
        # made `launch` proceed and `status` print ok on the one channel that silently outranks
        # the gateway. Malformed JSON is the reachable case; a missing jq behaves the same way.
        result, log = self.run_launcher("launch", global_settings_raw="{not json")

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("could not be checked", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_an_absent_settings_document_is_a_clean_state_not_a_gap(self) -> None:
        # The inverse: a fresh machine has no settings.json at all, and that must launch.
        result, _ = self.run_launcher("launch")

        self.assertEqual(result.returncode, 0, result.stderr)

    # ONE fixture list per verdict, consumed by BOTH base-URL channels below. The launcher feeds its
    # two channels from one shared loopback pattern for the same reason: a fixture list per channel
    # is how "refuses from the shell, passes silently from the file" gets reintroduced.
    FOREIGN_BASE_URLS = (
        "https://example.invalid",
        "http://gateway.example.test:8080",
        # https to a plaintext local hop is not the route this launch prepares.
        "https://127.0.0.1:10100",
        # A loopback-LOOKING host that is not loopback, and 127.0.0.1 smuggled into userinfo.
        "http://127.0.0.1.example.invalid",
        "http://127.0.0.1@example.invalid/",
    )
    LOOPBACK_BASE_URLS = (
        "http://127.0.0.1:10100",
        "http://localhost:10100",
        "HTTP://127.0.0.1:10100/",
        "http://[::1]:10100",
        "http://127.0.0.1",
    )

    def test_launch_refuses_a_foreign_base_url_in_the_global_settings_env(self) -> None:
        # This replaces a test that asserted the OPPOSITE and pinned a coverage regression. Its
        # premise -- "`ocx claude` sets ANTHROPIC_BASE_URL in the child PROCESS env, which Claude
        # Code resolves above settings `env`" -- is disproved. Measured against 2.1.227 with two
        # loopback listeners, :59998 exported and :59999 in settings `env`: all six
        # POST /v1/messages went to :59999. Settings `env` wins unless
        # CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST is set, and opencodex injects that only when it owns
        # an auth token -- which this subscription route deliberately never does.
        for value in self.FOREIGN_BASE_URLS:
            with self.subTest(value=value):
                result, log = self.run_launcher(
                    "launch", global_settings={"env": {"ANTHROPIC_BASE_URL": value}}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_BASE_URL", result.stderr)
                self.assertIn("settings.json", result.stderr)
                # It must not claim to have routed anything it did not route.
                self.assertNotIn("routed at", result.stdout)
                # A base URL can carry userinfo credentials, so the value is never echoed.
                self.assertNotIn(value, result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_launch_accepts_a_loopback_base_url_in_the_global_settings_env(self) -> None:
        # The other half of the same check: the gateway's port is not known until ensure_gateway_up
        # has run, and starting a gateway to decide a refusal would leave a proxy behind a refused
        # launch. So the rule is shape-based -- an http loopback URL is benign -- and refusing one
        # would block a setup that works.
        for value in self.LOOPBACK_BASE_URLS:
            with self.subTest(value=value):
                result, _ = self.run_launcher(
                    "launch", global_settings={"env": {"ANTHROPIC_BASE_URL": value}}
                )

                self.assertEqual(result.returncode, 0, result.stderr)

    def test_launch_refuses_a_foreign_exported_base_url(self) -> None:
        # The mirror of the settings check, and it was an explicitly UNCLOSED gap until it was
        # measured on 2026-08-11. Two loopback capture listeners, each replying 400 and forwarding
        # nothing; `ANTHROPIC_BASE_URL=http://127.0.0.2:59991` exported; the REAL `ocx claude` path
        # against a healthy gateway on 127.0.0.1:10100 with a dummy sk-ant-oat01 sentinel:
        # HEAD /api/hello, GET /v1/models and POST /v1/messages all arrived at :59991 and the
        # gateway saw nothing. A stub `claude` in the same run showed why -- the child environment
        # opencodex built carried the foreign value and no gateway value at all, because `bin/ocx.mjs`
        # proves which slots the shell exported and buildClaudeEnv's setDefault then declines to
        # overwrite one ("user wins"). So an exported foreign value is a live bypass that carries the
        # operator's own login to that address.
        for value in self.FOREIGN_BASE_URLS:
            with self.subTest(value=value):
                result, log = self.run_launcher("launch", parent_env={"ANTHROPIC_BASE_URL": value})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_BASE_URL", result.stderr)
                self.assertIn("exported", result.stderr)
                self.assertNotIn("routed at", result.stdout)
                # A base URL can carry userinfo credentials, so the value is never echoed.
                self.assertNotIn(value, result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_launch_accepts_a_loopback_exported_base_url(self) -> None:
        # Measured control for the same run: with `ANTHROPIC_BASE_URL=http://127.0.0.1:59992`
        # exported -- loopback, wrong port -- opencodex printed "Replacing stale opencodex
        # ANTHROPIC_BASE_URL ... with http://127.0.0.1:10100", that listener saw nothing, and the
        # turn reached Anthropic through the gateway. Refusing a loopback shape would therefore
        # block a launch that opencodex itself repairs. The same fixtures as the settings channel,
        # so the two cannot diverge.
        for value in self.LOOPBACK_BASE_URLS:
            with self.subTest(value=value):
                result, log = self.run_launcher("launch", parent_env={"ANTHROPIC_BASE_URL": value})

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<ocx><claude>", log.read_text())

    def test_an_empty_exported_base_url_is_not_read_as_a_destination(self) -> None:
        # Empty names nothing, and opencodex's setDefault treats it as absent and fills in the live
        # gateway. Refusing it would refuse the ordinary case of a variable cleared in a profile.
        result, _ = self.run_launcher("launch", parent_env={"ANTHROPIC_BASE_URL": ""})

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launch_refuses_every_switch_in_the_clients_provider_table(self) -> None:
        # The earlier check enumerated Bedrock/Vertex/Foundry only. 2.1.227's own provider table
        # also carries the AWS and Google-Cloud switches, and CLAUDE_CODE_USE_ANTHROPIC_AWS=1 was
        # measured to make the client demand AWS_REGION with nothing reaching a local listener --
        # it left the ANTHROPIC_BASE_URL path entirely. On a host that already exports AWS_REGION
        # (common) that turn bills the cloud account under a gateway banner.
        # CLAUDE_CODE_USE_MANTLE was that table's last uncovered switch, refused here only from
        # 2026-08-11 and only on measurement: with the base URL pointed at a loopback capture
        # listener, the switch ALONE never contacted it (the client hung resolving AWS credentials);
        # with AWS_REGION and a dummy bearer it reported "Enable Opus 5 in Amazon Bedrock (Mantle)"
        # then a 401 from AWS; and with ANTHROPIC_BEDROCK_MANTLE_BASE_URL pointed at a second
        # listener every POST /v1/messages went there. It needs no companion variable to defeat this
        # route -- the client's provider resolver returns "mantle" for a truthy value of it alone.
        for name in (
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
            "CLAUDE_CODE_USE_FOUNDRY",
            "CLAUDE_CODE_USE_ANTHROPIC_AWS",
            "CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD",
            "CLAUDE_CODE_USE_MANTLE",
        ):
            with self.subTest(name=name, channel="exported"):
                result, log = self.run_launcher("launch", parent_env={name: "1"})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertNotIn("routed at", result.stdout)
                self.assertOnlyReadOnlyOcxRoutes(log)
            with self.subTest(name=name, channel="settings"):
                result, log = self.run_launcher("launch", global_settings={"env": {name: "1"}})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertIn("settings.json", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_launch_refuses_every_endpoint_slot_in_the_clients_provider_table(self) -> None:
        # The endpoint and credential slots are the second half of the same table. These are read
        # by VALUE rather than as booleans, so a non-empty value is the trigger.
        for name in (
            "AWS_BEARER_TOKEN_BEDROCK",
            "ANTHROPIC_BEDROCK_BASE_URL",
            "ANTHROPIC_VERTEX_BASE_URL",
            "ANTHROPIC_AWS_BASE_URL",
            "ANTHROPIC_GOOGLE_CLOUD_BASE_URL",
            "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
        ):
            value = "OCXTESTSENTINEL-not-a-real-endpoint"
            with self.subTest(name=name, channel="exported"):
                result, log = self.run_launcher("launch", parent_env={name: value})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertNotIn("OCXTESTSENTINEL", result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)
            with self.subTest(name=name, channel="settings"):
                result, log = self.run_launcher("launch", global_settings={"env": {name: value}})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertNotIn("OCXTESTSENTINEL", result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_disabled_provider_switch_does_not_refuse_a_working_launch(self) -> None:
        # Measured: with CLAUDE_CODE_USE_BEDROCK=0 the traffic still went to ANTHROPIC_BASE_URL, so
        # refusing on presence alone stopped a launch that works -- and `=0` is exactly how an
        # operator disables a switch inherited from a profile or a wrapper. Both channels must agree
        # on that, which they did not while one tested emptiness and the other tested key presence.
        for value in ("0", "", "false", "FALSE", " false "):
            with self.subTest(value=value, channel="exported"):
                result, _ = self.run_launcher(
                    "launch", parent_env={"CLAUDE_CODE_USE_BEDROCK": value}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
            with self.subTest(value=value, channel="settings"):
                result, _ = self.run_launcher(
                    "launch", global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": value}}
                )

                self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_enabled_provider_switch_still_refuses_in_both_channels(self) -> None:
        # Truthiness must not become a bypass: anything that is not "", "0" or "false" is enabled.
        for value in ("1", "true", "TRUE", "on"):
            with self.subTest(value=value, channel="exported"):
                result, _ = self.run_launcher(
                    "launch", parent_env={"CLAUDE_CODE_USE_VERTEX": value}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("CLAUDE_CODE_USE_VERTEX", result.stderr)
            with self.subTest(value=value, channel="settings"):
                result, _ = self.run_launcher(
                    "launch", global_settings={"env": {"CLAUDE_CODE_USE_VERTEX": value}}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("CLAUDE_CODE_USE_VERTEX", result.stderr)

    def test_an_empty_endpoint_slot_is_not_read_as_a_configured_route(self) -> None:
        # The value-based half of the same consistency: an empty endpoint names no destination, so
        # it must not refuse. The settings channel used to refuse it on key presence alone.
        result, _ = self.run_launcher("launch", parent_env={"ANTHROPIC_BEDROCK_BASE_URL": ""})
        self.assertEqual(result.returncode, 0, result.stderr)

        result, _ = self.run_launcher(
            "launch", global_settings={"env": {"ANTHROPIC_BEDROCK_BASE_URL": ""}}
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_dangling_settings_symlink_is_treated_as_no_settings_at_all(self) -> None:
        # Claude Code reads this path and treats ENOENT as no settings, so a dotfile symlink whose
        # target moved carries no key that could outrank the gateway. Admitting it as absent matches
        # the client; failing closed there would hard-stop a working launch over a broken dotfile.
        result, _ = self.run_launcher("launch")
        settings = self.global_claude / "settings.json"
        self.global_claude.mkdir(parents=True, exist_ok=True)
        settings.symlink_to(self.global_claude / "moved-away.json")

        second = subprocess.run(
            [BASH, str(SCRIPT), "launch"],
            text=True, capture_output=True, check=False, env=self.launch_env,
            cwd=str(self.project),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)

    # --- the project-scoped documents (measured 2026-08-11) --------------------------------
    #
    # Reading only ~/.claude/settings.json left two documents unchecked while `status` printed
    # "nothing in this shell or the global settings document outranks the gateway". Measured against
    # 2.1.227 with one listener named in the document and a second exported: for BOTH
    # ./.claude/settings.json and ./.claude/settings.local.json the early HEAD /api/hello went to the
    # exported value and every POST /v1/messages went to the document's -- so a bypass there is not
    # theoretical, and an early probe reaching the gateway is not evidence of a routed session.

    def test_launch_refuses_a_bypassing_key_in_a_project_settings_document(self) -> None:
        for document in ("project_settings", "project_settings_local"):
            for payload, expected in (
                ({"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}}, "CLAUDE_CODE_USE_BEDROCK"),
                ({"env": {"ANTHROPIC_BASE_URL": "https://example.invalid"}}, "ANTHROPIC_BASE_URL"),
                ({"env": {"ANTHROPIC_API_KEY": "sk-ant-api03-OCXTESTSENTINEL"}}, "ANTHROPIC_API_KEY"),
                ({"apiKeyHelper": "/bin/echo"}, "apiKeyHelper"),
            ):
                with self.subTest(document=document, key=expected):
                    result, log = self.run_launcher("launch", **{document: payload})

                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn(expected, result.stderr)
                    # The refusal must name the document it actually read, not the global one.
                    self.assertIn(".claude/settings", result.stderr)
                    self.assertNotIn("routed at", result.stdout)
                    self.assertNotIn("OCXTESTSENTINEL", result.stdout + result.stderr)
                    self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_project_settings_document_refusal_names_that_document(self) -> None:
        # A refusal that named the global path for a project-scoped key would send the operator to
        # edit a file that does not contain it.
        result, _ = self.run_launcher(
            "launch", project_settings_local={"env": {"CLAUDE_CODE_USE_VERTEX": "1"}}
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn(f"{self.project}/.claude/settings.local.json", result.stderr)

    def test_a_clean_project_document_does_not_refuse(self) -> None:
        # The project documents are ordinary files that usually carry permissions and hooks. Only a
        # routing key, an apiKeyHelper or a Console-shaped value may stop a launch.
        result, _ = self.run_launcher(
            "launch",
            project_settings={"permissions": {"allow": ["Bash"]}, "env": {"FOO": "bar"}},
            project_settings_local={"env": {"CLAUDE_CODE_USE_BEDROCK": "0"}},
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_global_settings_local_sibling_is_not_read_for_env(self) -> None:
        # A MEASURED negative, pinned so the document list does not grow by symmetry: with
        # env.ANTHROPIC_BASE_URL in <global>/settings.local.json and a different value exported,
        # every request went to the EXPORTED value -- the client does not read that file for `env`.
        # Refusing on it would stop a launch over a document Claude Code ignores.
        result, log = self.run_launcher(
            "launch",
            global_settings_local={"env": {
                "ANTHROPIC_BASE_URL": "https://example.invalid",
                "CLAUDE_CODE_USE_BEDROCK": "1",
            }},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_launch_help_names_exactly_the_documents_it_checks(self) -> None:
        # The help text is the operator-facing version of the same claim, so it must not describe a
        # surface wider than the one measured.
        result, _ = self.run_launcher("launch", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        for document in (
            "~/.claude/settings.json",
            "./.claude/settings.json",
            "./.claude/settings.local.json",
        ):
            self.assertIn(document, result.stdout)
        self.assertIn("NOT checked", result.stdout)
        self.assertIn("managed", result.stdout)

    def test_status_names_the_documents_it_checked_instead_of_claiming_all_of_them(self) -> None:
        result, _ = self.run_launcher("status")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing exported in this shell", result.stdout)
        for document in (
            f"checked: {self.home}/.claude/settings.json",
            f"checked: {self.project}/.claude/settings.json",
            f"checked: {self.project}/.claude/settings.local.json",
        ):
            self.assertIn(document, result.stdout)
        self.assertIn("NOT checked: enterprise managed policy", result.stdout)
        # The overreaching sentence this replaced must not come back.
        self.assertNotIn("nothing in this shell or the global settings document", result.stdout)

    def test_status_lists_a_document_once_when_the_launch_directory_is_home(self) -> None:
        # Launching from your home directory makes the project entry the global one. Printing the
        # same path twice would read as two independent documents having been checked.
        self.run_launcher("status")
        self.home.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [BASH, str(SCRIPT), "status"],
            text=True, capture_output=True, check=False, env=self.launch_env,
            cwd=str(self.home),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        listed = [line for line in result.stdout.splitlines() if "checked: " in line]
        self.assertEqual(sorted(listed), sorted(set(listed)), listed)
        self.assertEqual(
            len([line for line in listed if line.endswith("/.claude/settings.json")]), 1, listed
        )

    def test_status_reports_a_project_scoped_bypass_rather_than_ok(self) -> None:
        result, _ = self.run_launcher(
            "status", project_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BYPASSED", result.stdout)
        self.assertIn(f"{self.project}/.claude/settings.json", result.stdout)
        self.assertNotIn("nothing exported in this shell", result.stdout)

    def test_status_reports_an_exported_foreign_base_url_without_echoing_it(self) -> None:
        result, _ = self.run_launcher(
            "status", parent_env={"ANTHROPIC_BASE_URL": "https://example.invalid"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BYPASSED", result.stdout)
        self.assertIn("ANTHROPIC_BASE_URL", result.stdout)
        self.assertNotIn("example.invalid", result.stdout + result.stderr)

    def test_launch_ships_the_opinionated_compaction_default_without_overriding_the_operator(self) -> None:
        # ADR-0012 decision 4. This used to ride along with the env scrub that ADR-0014 deleted.
        default_run, _ = self.run_launcher("launch")
        self.assertEqual(default_run.returncode, 0, default_run.stderr)
        self.assertIn("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85", self.env_log.read_text())

        chosen, _ = self.run_launcher("launch", parent_env={"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "40"})
        self.assertEqual(chosen.returncode, 0, chosen.stderr)
        self.assertIn("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=40", self.env_log.read_text())

    def test_launch_refuses_an_apikeyhelper_that_would_displace_the_login(self) -> None:
        result, log = self.run_launcher("launch", global_settings={"apiKeyHelper": "/bin/echo"})

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("apiKeyHelper", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_launch_refuses_a_console_key_without_echoing_it(self) -> None:
        # sk-ant-api* satisfies opencodex's bare sk-ant- passthrough gate, so it takes the SAME
        # native branch and bills API credits while looking like subscription traffic.
        secret = "sk-ant-api03-OCXTESTSENTINEL"
        result, log = self.run_launcher("launch", parent_env={"ANTHROPIC_API_KEY": secret})

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("ANTHROPIC_API_KEY", result.stderr)
        self.assertIn("credits", result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_launch_accepts_a_subscription_shaped_oauth_token(self) -> None:
        # The inverse of the case above, and the one ADR-0003 used to refuse outright: an
        # sk-ant-oat* login is exactly what this route now exists to carry.
        result, log = self.run_launcher(
            "launch", parent_env={"ANTHROPIC_AUTH_TOKEN": "sk-ant-oat01-OCXTESTSENTINEL"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        # Exit 0 cannot distinguish "launched" from "did nothing quietly": the trace can.
        self.assertIn("<ocx><claude>", log.read_text())

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
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_configure_refuses_custom_anthropic_endpoint_without_printing_secret(self) -> None:
        secret = "OCX_TEST_SECRET"
        result, log = self.run_launcher(
            "configure", "provider", "add", "harmless-name",
            "--adapter", "openai-chat", "--base-url", "HTTPS://API.ANTHROPIC.COM:443/v1",
            "--api-key", secret,
        )

        self.assertEqual(result.returncode, 3)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

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
        self.assertOnlyReadOnlyOcxRoutes(log)

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
        self.assertOnlyReadOnlyOcxRoutes(log)

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
                self.assertOnlyReadOnlyOcxRoutes(log)

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
        self.assertOnlyReadOnlyOcxRoutes(log)

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
            cwd=str(self.project),
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
            cwd=str(self.project),
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
            cwd=str(self.project),
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
