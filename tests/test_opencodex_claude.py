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


@unittest.skipIf(
    BASH is None or os.name == "nt",
    "bash launcher fixtures require a POSIX bash; Git Bash's MSYS path/argv conversion"
    " rewrites argv and paths",
)
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
        selected_settings_raw: str | None = None,
        selected_settings_name: str = "selected-settings.json",
        selected_settings_mode: int | None = None,
        selected_settings_directory: bool = False,
        remove_selected_settings_before_open: bool = False,
        hostile_path_jq: bool = False,
        bound_jq_refuses_default_provider_read: bool = False,
        bound_jq_missing: bool = False,
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
        # `claude_settings_documents` now canonicalizes `$HOME` and `$PWD` itself, so an unresolved
        # HOME no longer makes one document count twice -- that is the launcher's job and
        # test_status_lists_a_document_once_when_home_is_a_second_spelling_of_the_launch_directory
        # is what holds it to it. What resolving the root still buys is agreement: the launcher
        # prints the PHYSICAL spelling, so an unresolved `self.project` would make every
        # `checked: <path>` and every refusal-names-this-document assertion compare against a path
        # the launcher never emits.
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
        self.selected_settings = self.project / selected_settings_name
        if selected_settings_directory:
            self.selected_settings.mkdir(parents=True, exist_ok=True)
        elif selected_settings_raw is not None:
            self.selected_settings.parent.mkdir(parents=True, exist_ok=True)
            self.selected_settings.write_text(selected_settings_raw)
            if selected_settings_mode is not None:
                self.selected_settings.chmod(selected_settings_mode)
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
        # `assertFalse(log.exists())` pass for the wrong reason. Assertions in BOTH directions --
        # "no MUTATION ran" and "this route WAS forwarded" -- now check the trace CONTENT, because
        # `require_ocx` legitimately runs `ocx --version` first: that is neither a mutation nor
        # evidence that anything else ran. See traced_ocx_route below.
        self.ocx_trace_log = root / "ocx-trace.log"
        log = self.ocx_trace_log

        mise = bin_dir / "mise"
        # Record every `ocx` invocation before fixture dispatch, so tests can prove exact
        # preflight ordering instead of mistaking an unlogged special case for no interaction.
        # Pinned `jq` resolution is a separate tool call and is not part of the gateway log.
        mise.write_text(
            "#!/bin/sh\n"
            'case " $* " in *" which ocx ") printf "%s/ocx\\n" "$(dirname "$0")"; exit 0 ;; esac\n'
            "while [ \"$#\" -gt 0 ] && [ \"$1\" != -- ]; do shift; done\n"
            "[ \"${1:-}\" = -- ] && shift\n"
            "if [ \"${1:-}\" = jq ]; then shift; exec \"${TEST_REAL_JQ:-jq}\" \"$@\"; fi\n"
            "printf '<%s>' \"$@\" >> \"$OCX_TRACE_LOG\"\n"
            "printf '\\n' >> \"$OCX_TRACE_LOG\"\n"
            "if [ \"${1:-}\" = bash ]; then export PATH=\"$(dirname \"$0\"):$PATH\"; exec \"$@\"; fi\n"
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
        ocx = bin_dir / "ocx"
        ocx.write_text(
            "#!/bin/sh\n"
            "printf '<ocx>' >> \"$OCX_TRACE_LOG\"\n"
            "printf '<%s>' \"$@\" >> \"$OCX_TRACE_LOG\"\n"
            "printf '\\n' >> \"$OCX_TRACE_LOG\"\n"
            'if [ "${1:-}" = claude ]; then shift; exec claude "$@"; fi\n'
            "exit ${OCX_EXIT:-0}\n"
        )
        ocx.chmod(0o755)
        # curl stub: serves the gateway catalog fixture for /v1/models and fails for
        # /healthz so uptime stays a nicety. CATALOG_JSON empty => unreachable catalog.
        #
        # IT TRACES TOO, into the SAME log and with a `<curl>` first field. The script does not
        # reach the gateway through `ocx` alone -- gateway_uptime_seconds, gateway_half_up and
        # live_catalog_model_ids each talk HTTP to it directly -- so while only `ocx` was traced,
        # every "must not have contacted a gateway" comment in this file was an assertion the
        # evidence could not support. The distinct prefix is what lets
        # assertOnlyReadOnlyOcxRoutes classify an HTTP contact as contact rather than as an
        # unparseable ocx route.
        curl = bin_dir / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            "{ printf '<curl>'; for argument in \"$@\"; do printf '<%s>' \"$argument\"; done;\n"
            "  printf '\\n'; } >> \"$OCX_TRACE_LOG\"\n"
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
        # THE `jq` ON PATH IS NOT THE ONE THE LAUNCHER USES, and since 2026-08-21 that is the point
        # rather than an accident. `scripts/opencodex-claude.sh` resolves jq from exactly two
        # admitted routes -- `$AGENTIC_SDLC_JQ`, then `mise -C <root> exec -- jq` -- and never from
        # PATH (ADR-0020). So this symlink stays planted as AMBIENT state the launcher must ignore,
        # the mise stub above serves the pinned route from `$TEST_REAL_JQ`, and a test that needs to
        # OBSERVE the tool binds it through `$AGENTIC_SDLC_JQ` below.
        jq = shutil.which("jq")
        if jq:
            jq_command = bin_dir / "jq"
            if hostile_path_jq:
                # A DIFFERENT jq at the head of PATH: it records that it ran, then answers `clean`
                # to every program, which is the shape that would silently suppress every settings
                # refusal in the launcher. Nothing here may ever invoke it.
                jq_command.write_text(
                    "#!/bin/sh\n"
                    'printf "invoked <%s>\\n" "$*" >> "$OCX_TEST_HOSTILE_JQ_MARKER"\n'
                    'if [ "${1:-}" = --version ]; then printf "jq-1.8.2\\n"; exit 0; fi\n'
                    'printf "clean\\n"\n'
                    "exit 0\n"
                )
                jq_command.chmod(0o755)
                # The SAME stub under a second, non-`jq` name. A test that binds `AGENTIC_SDLC_JQ`
                # to the bare name `jq` would recurse into the shell function until bash dies, so
                # the bare-name channel is demonstrated with a name that would resolve through
                # ambient PATH to a real executable instead of back into this file.
                shim = bin_dir / "jq-shim"
                shim.write_text(jq_command.read_text())
                shim.chmod(0o755)
            else:
                jq_command.symlink_to(jq)
        # THE TWO OBSERVABLE STUBS BELOW ARE BOUND AS THE EXACT jq (`$AGENTIC_SDLC_JQ`, the
        # operator-tools binding), never planted on PATH: PATH is not a resolution channel any more,
        # so a stub left there would simply never be reached and the state each fixture exists to
        # create would never be entered. Both forward everything they do not intercept to the real
        # jq, so the classification under test stays the real one.
        #
        # This one refuses exactly ONE of the reads `status` makes -- the configured-default lookup,
        # identified by its program text rather than by a call number, so the fixture does not rot
        # when a jq call is added elsewhere. That leaves the comparison genuinely half-complete,
        # which is the only state that can produce the false NOT-LIVE the default-provider read is
        # fail-closed to prevent.
        if bound_jq_refuses_default_provider_read:
            partial_jq = bin_dir / "bound-partial-jq"
            partial_jq.write_text(
                "#!/bin/sh\n"
                'case " $* " in *isDefault*) exit 127 ;; esac\n'
                'exec "$TEST_REAL_JQ" "$@"\n'
            )
            partial_jq.chmod(0o755)
        # And this one counts availability probes and deletes the selected settings file on the
        # second, which is what opens the window between the readability check and the open.
        if remove_selected_settings_before_open:
            counting_jq = bin_dir / "bound-counting-jq"
            counting_jq.write_text(
                "#!/bin/sh\n"
                'if [ "${1:-}" = --version ]; then\n'
                '  count=0; [ ! -f "$OCX_TEST_JQ_COUNT" ] || read -r count < "$OCX_TEST_JQ_COUNT"\n'
                '  count=$((count + 1)); printf "%s\\n" "$count" > "$OCX_TEST_JQ_COUNT"\n'
                '  [ "$count" -ne 2 ] || rm -f -- "$OCX_TEST_SELECTED_SETTINGS"\n'
                'fi\n'
                'exec "$TEST_REAL_JQ" "$@"\n'
            )
            counting_jq.chmod(0o755)
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
        # Absent unless the hostile PATH `jq` above actually ran, which is the assertion.
        self.hostile_jq_marker = root / "hostile-jq-invoked.txt"
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
            "OCX_TEST_SELECTED_SETTINGS": str(self.selected_settings),
            "OCX_TEST_JQ_COUNT": str(root / "jq-count"),
            "OCX_TEST_HOSTILE_JQ_MARKER": str(self.hostile_jq_marker),
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
        if remove_selected_settings_before_open:
            env["AGENTIC_SDLC_JQ"] = str(bin_dir / "bound-counting-jq")
        if bound_jq_refuses_default_provider_read:
            env["AGENTIC_SDLC_JQ"] = str(bin_dir / "bound-partial-jq")
        if bound_jq_missing:
            # The bound exact executable is gone (a retired toolchain, a moved install) while a
            # perfectly good jq stays on PATH. Neither route may borrow the other's copy.
            env["AGENTIC_SDLC_JQ"] = str(bin_dir / "no-such-bound-jq")
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
    #
    # THE SHARED SET IS ONE LINE, deliberately. `<ocx><config><show><--json>` was in it, which meant
    # every caller admitted a config read whether or not its route classifies a provider -- and only
    # two of the eighteen callers actually reach it (the renamed-Anthropic-provider pair, which must
    # read the config to classify the rename). The rest now prove they refused without reading the
    # config at all. A caller that legitimately needs one more read-only route names it through
    # `also_admitted`, which is why widening is cheap and blanket admission is not.
    ADMITTED_READ_ONLY_OCX_ROUTES = (
        # require_ocx's own liveness probe, run before every route including a refused one.
        "<ocx><--version>",
    )

    def assertOnlyReadOnlyOcxRoutes(self, log: Path, *also_admitted: str) -> None:
        """Fail unless every traced gateway interaction is an admitted read-only one.

        The trace carries TWO kinds of line: `<ocx>...` for a routed CLI invocation and
        `<curl>...` for a direct HTTP contact with the gateway (see the curl stub). Both are
        classified here, and no `<curl>` line is admitted by default -- an HTTP probe IS contact,
        so a test whose comment says the gateway was never contacted now depends on that being
        checked rather than assumed. No path this assertion currently guards makes an HTTP call,
        so the strict default costs nothing today and fails loudly if a refusal is ever reordered
        below a probe.

        `also_admitted` widens the set for a test that legitimately reaches one more read-only
        route; it never narrows it, and a mutation is unreachable through it because the caller
        has to name the exact line.
        """
        admitted = set(self.ADMITTED_READ_ONLY_OCX_ROUTES) | set(also_admitted)
        trace = log.read_text() if log.exists() else ""
        unexpected = [line for line in trace.splitlines() if line.strip() and line not in admitted]
        self.assertEqual(
            unexpected,
            [],
            f"traced a gateway interaction outside the admitted set {sorted(admitted)}",
        )

    # THE MIRROR-IMAGE VACUITY. `assertOnlyReadOnlyOcxRoutes` closed the negative direction; the
    # POSITIVE direction was still being asserted with `assertTrue(log.exists())` and with exit 0,
    # and neither is route evidence. `require_ocx` runs `ocx --version` before any route is
    # forwarded, so the trace file exists on every path that gets as far as running -- the preflight
    # alone satisfies the assertion. MEASURED on 2026-08-11: replacing cmd_configure's
    # `ocx "$@" || status=$?` with a no-op failed 6 of 69 tests, while six more kept passing with
    # the entire `configure` passthrough gutted -- including the one asserting the "NOT LIVE YET /
    # run `ocx sync`" advice, which is a FALSE INSTRUCTION when the mutation never ran.
    #
    # So a test that means "this route was forwarded" names the exact traced line. The expectation
    # is built from the arguments the TEST passes, never from anything the launcher computes, so it
    # cannot drift into agreeing with a broken passthrough.
    @staticmethod
    def traced_ocx_route(*arguments: str) -> str:
        """The line the mise stub writes for `ocx <arguments>` (`printf '<%s>'` over argv)."""
        return "".join(f"<{field}>" for field in ("ocx", *arguments))

    def assertExactTraceLine(self, log: Path, expected: str) -> None:
        self.assertIn(expected, log.read_text().splitlines())

    def assertExactTracedOcxRoute(self, log: Path, *arguments: str) -> None:
        self.assertExactTraceLine(log, self.traced_ocx_route(*arguments))

    def test_exact_route_assertion_rejects_appended_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "trace.log"
            log.write_text("<ocx><claude><--model><gpt><--duplicated>\n")

            with self.assertRaises(AssertionError):
                self.assertExactTracedOcxRoute(log, "claude", "--model", "gpt")

    def test_redacted_full_route_assertion_rejects_appended_arguments(self) -> None:
        secret = "OCX_TEST_SECRET"
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "trace.log"
            log.write_text(f"<ocx><provider><add><--api-key><{secret}><--duplicated>\n")

            with self.assertRaises(AssertionError) as raised:
                self.assertFullRouteWithRedactedFailure(
                    log, "provider", "add", "--api-key", secret
                )

        self.assertNotIn(secret, str(raised.exception))

    def assertFullRouteWithRedactedFailure(self, log: Path, *arguments: str) -> None:
        """Assert the COMPLETE traced route, including any credential, without printing it.

        The credential-route tests have two obligations that pull against each other: the
        expectation must cover the key flag AND its value (a route expectation that stops at
        `--base-url` passes against a wrapper that drops `--api-key` before forwarding -- the
        precise silent drop those tests exist to catch), while a failure must not put the value in
        the output of a test whose sibling assertion is that it is never printed.

        `assertIn`'s standard failure message prints both operands, so it would dump the value and
        the whole trace. `unittest` APPENDS a custom `msg` to that standard message by default;
        `longMessage = False` makes `msg` REPLACE it. That is what lets the comparison stay exact
        while the diagnostic stays redacted. Set on the instance, so it is scoped to the one test
        method that calls this (each test runs on a fresh instance).

        The values these callers pass are test sentinels, not real secrets. The habit is the point:
        a helper that cannot leak is what keeps the next author from re-truncating the expectation.
        """
        redacted = self.traced_ocx_route(
            *("<redacted>" if index > 0 and arguments[index - 1].endswith("-key") else argument
              for index, argument in enumerate(arguments))
        )
        self.longMessage = False
        self.assertIn(
            self.traced_ocx_route(*arguments),
            log.read_text().splitlines(),
            f"the complete route was not forwarded; expected (redacted): {redacted}",
        )

    def test_ultracode_injects_exact_setting_and_preserves_arguments(self) -> None:
        result, log = self.run_launcher("launch-ultracode", "--model", "gpt-5.6-sol")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertExactTraceLine(
            log, '<ocx><claude><--settings><{"ultracode":true}><--model><gpt-5.6-sol>'
        )

    def test_yolo_is_an_orthogonal_owned_flag_on_both_launch_profiles(self) -> None:
        cases = (
            (
                ("launch", "--yolo", "--model", "gpt-5.6-sol"),
                "<ocx><claude><--dangerously-skip-permissions><--model><gpt-5.6-sol>",
            ),
            (
                ("launch-ultracode", "--yolo", "--model", "gpt-5.6-sol"),
                "<ocx><claude><--dangerously-skip-permissions><--settings>"
                "<{\"ultracode\":true}><--model><gpt-5.6-sol>",
            ),
        )
        for arguments, expected_route in cases:
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher(*arguments)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTraceLine(log, expected_route)
                self.assertNotIn("<--yolo>", log.read_text())
                self.assertIn("permissions: BYPASSED", result.stdout)

    def test_yolo_refuses_competing_permission_controls_before_ocx(self) -> None:
        for route in ("launch", "launch-ultracode"):
            for conflict in (
                ("--dangerously-skip-permissions",),
                ("--dangerously-skip-permissions=true",),
                ("--allow-dangerously-skip-permissions",),
                ("--allow-dangerously-skip-permissions=true",),
                ("--permission-mode=bypassPermissions",),
                ("--permission-mode", "plan"),
            ):
                with self.subTest(route=route, conflict=conflict):
                    result, log = self.run_launcher(route, "--yolo", *conflict)

                    self.assertEqual(result.returncode, 3)
                    self.assertIn("REFUSED", result.stderr)
                    self.assertIn("--yolo", result.stderr)
                    self.assertFalse(log.exists())

    def test_forwarding_separator_keeps_a_literal_yolo_argument(self) -> None:
        for route, expected in (
            ("launch", "<ocx><claude><--yolo>"),
            ("launch-ultracode", '<ocx><claude><--settings><{"ultracode":true}><--yolo>'),
        ):
            with self.subTest(route=route):
                result, log = self.run_launcher(route, "--", "--yolo")

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTraceLine(log, expected)
                self.assertNotIn("permissions: BYPASSED", result.stdout)

    def test_wrapper_validation_stops_at_claudes_option_terminator(self) -> None:
        cases = (
            (
                ("launch", "--yolo", "--", "--permission-mode", "auto"),
                "<ocx><claude><--dangerously-skip-permissions><--><--permission-mode><auto>",
            ),
            (
                ("launch", "--model", "gpt-5.6-sol", "--", "--yolo"),
                "<ocx><claude><--model><gpt-5.6-sol><--><--yolo>",
            ),
            (
                ("launch-ultracode", "--", "--", "--settings", "literal"),
                '<ocx><claude><--settings><{"ultracode":true}><--><--settings><literal>',
            ),
        )
        for arguments, expected_route in cases:
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher(*arguments)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTraceLine(log, expected_route)

    def test_unescaped_yolo_must_be_the_first_wrapper_argument(self) -> None:
        for route in ("launch", "launch-ultracode"):
            with self.subTest(route=route):
                result, log = self.run_launcher(route, "--model", "gpt-5.6-sol", "--yolo")

                self.assertEqual(result.returncode, 3)
                self.assertIn("REFUSED", result.stderr)
                self.assertIn("must be the first", result.stderr)
                self.assertFalse(log.exists())

    def test_ultracode_refuses_competing_settings_before_ocx(self) -> None:
        secret = "OCX_ULTRACODE_SETTINGS_SECRET"
        for arguments in (
            ("--settings", f'{{"token":"{secret}"}}'),
            (f'--settings={{"token":"{secret}"}}',),
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("launch-ultracode", *arguments)

                self.assertEqual(result.returncode, 3)
                self.assertIn("REFUSED", result.stderr)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertFalse(log.exists())

    def test_ultracode_refuses_permission_bypass_before_ocx(self) -> None:
        for arguments in (
            ("--dangerously-skip-permissions",),
            ("--dangerously-skip-permissions=true",),
            ("--allow-dangerously-skip-permissions",),
            ("--allow-dangerously-skip-permissions=true",),
            ("--permission-mode=bypassPermissions",),
            ("--permission-mode", "bypassPermissions"),
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("launch-ultracode", *arguments)
                self.assertEqual(result.returncode, 3)
                self.assertFalse(log.exists())

    def test_ordinary_launch_keeps_argument_boundaries(self) -> None:
        payload = '{"custom":"OCX_SETTINGS_VALUE"}'
        for arguments in (
            ("--settings", payload, "two words"),
            (f"--settings={payload}", "two words"),
            ("--", "--settings", payload, "two words"),
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("launch", *arguments)

                self.assertEqual(result.returncode, 0, result.stderr)
                forwarded = arguments[1:] if arguments[0] == "--" else arguments
                self.assertExactTracedOcxRoute(log, "claude", *forwarded)
                self.assertNotIn("OCX_SETTINGS_VALUE", result.stdout + result.stderr)

    def test_a_prompt_after_either_separator_reaches_ocx_claude_with_both_tokens(self) -> None:
        """agentic-sdlc-c773's regression case: `launch -- -p <string>` must deliver BOTH tokens.

        Two live observations had a prompt arrive at the model as a bare `-p`, and `-- --help`
        answered with the wrong program's help. This pins the half this repository owns — what the
        wrapper hands to `ocx claude` — and it holds: the leading wrapper `--` is consumed exactly
        once and a LATER literal `--` is forwarded in place with everything after it. Anything lost
        beyond this boundary is lost inside `ocx claude`, which this test cannot reach and the
        wrapper cannot fix; see the launcher's own note on the forwarded-shape banner.
        """
        prompt = "Reply with exactly: OCX_ROUTER_SENTINEL"
        cases = {
            "wrapper separator then a prompt": (("--", "-p", prompt), ("-p", prompt)),
            "later literal terminator": (
                ("--model", "gpt-5.4-mini", "--", "-p", prompt),
                ("--model", "gpt-5.4-mini", "--", "-p", prompt),
            ),
            "wrapper separator then a literal help request": (("--", "--help"), ("--help",)),
            "no separator at all": (("-p", prompt), ("-p", prompt)),
        }
        for name, (arguments, expected) in cases.items():
            with self.subTest(case=name):
                result, log = self.run_launcher("launch", *arguments)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTracedOcxRoute(log, "claude", *expected)
                # The prompt is a value: the banner must describe the shape and never echo it.
                self.assertNotIn("OCX_ROUTER_SENTINEL", result.stdout + result.stderr)

    def test_the_launch_banner_reports_the_forwarded_shape_without_any_value(self) -> None:
        # "[forwarded arguments withheld]" hid the defect above: from the outside there was no way
        # to see how many arguments the wrapper sent, or where the literal `--` sat among them.
        prompt = "Reply with exactly: OCX_BANNER_SENTINEL"
        result, _log = self.run_launcher("launch", "--model", "gpt-5.4-mini", "--", "-p", prompt)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"[5 forwarded: --model <value:12 chars> -- -p <value:{len(prompt)} chars>]", result.stdout)
        self.assertNotIn("OCX_BANNER_SENTINEL", result.stdout + result.stderr)
        self.assertNotIn("withheld", result.stdout)

        # Positive control: a launch with nothing forwarded says so, rather than printing an
        # empty list that reads the same as a suppressed one.
        bare, _bare_log = self.run_launcher("launch")
        self.assertEqual(bare.returncode, 0, bare.stderr)
        self.assertIn("[no forwarded arguments]", bare.stdout)

    def test_ordinary_launch_keeps_readable_settings_file_arguments(self) -> None:
        payload = '{"custom":"OCX_SETTINGS_FILE_VALUE"}'
        for setting_argument in ("--settings", "--settings=selected-settings.json"):
            with self.subTest(setting_argument=setting_argument):
                arguments = (
                    (setting_argument, "selected-settings.json")
                    if setting_argument == "--settings"
                    else (setting_argument,)
                )
                result, log = self.run_launcher(
                    "launch", *arguments, selected_settings_raw=payload
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTracedOcxRoute(log, "claude", *arguments)
                self.assertNotIn("OCX_SETTINGS_FILE_VALUE", result.stdout + result.stderr)

    def test_ordinary_launch_stops_scanning_settings_at_claudes_option_terminator(self) -> None:
        payload = '{"env":{"CLAUDE_CODE_USE_BEDROCK":"1"}}'
        arguments = ("prompt words", "--", "--settings", payload)

        result, log = self.run_launcher("launch", *arguments)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertExactTracedOcxRoute(log, "claude", *arguments)

    def test_ordinary_launch_refuses_bypassing_inline_settings_before_gateway_contact(self) -> None:
        payloads = (
            ('{"env":{"CLAUDE_CODE_USE_BEDROCK":"1"}}', "CLAUDE_CODE_USE_BEDROCK"),
            ('{"env":{"ANTHROPIC_BASE_URL":"https://example.invalid"}}', "ANTHROPIC_BASE_URL"),
            ('{"apiKeyHelper":"/bin/echo"}', "apiKeyHelper"),
            ('{"env":{"ANTHROPIC_API_KEY":"sk-ant-api-test"}}', "ANTHROPIC_API_KEY"),
        )
        for payload, key in payloads:
            for arguments in (
                ("--settings", payload),
                (f"--settings={payload}",),
                ("--", "--settings", payload),
            ):
                with self.subTest(key=key, arguments=arguments):
                    result, log = self.run_launcher("launch", *arguments)

                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn(key, result.stderr)
                    self.assertNotIn(payload, result.stdout + result.stderr)
                    self.assertNotIn("routed at", result.stdout)
                    self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_refuses_bypassing_settings_files_before_gateway_contact(self) -> None:
        selected_name = "selected-settings-OCX_PATH_SECRET.json"
        payloads = (
            ('{"env":{"CLAUDE_CODE_USE_BEDROCK":"1"}}', "CLAUDE_CODE_USE_BEDROCK"),
            ('{"env":{"ANTHROPIC_BASE_URL":"https://example.invalid"}}', "ANTHROPIC_BASE_URL"),
            ('{"apiKeyHelper":"/bin/echo"}', "apiKeyHelper"),
            ('{"env":{"ANTHROPIC_AUTH_TOKEN":"sk-ant-api-test"}}', "ANTHROPIC_AUTH_TOKEN"),
        )
        for payload, key in payloads:
            with self.subTest(key=key):
                result, log = self.run_launcher(
                    "launch",
                    f"--settings={selected_name}",
                    selected_settings_raw=payload,
                    selected_settings_name=selected_name,
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(key, result.stderr)
                self.assertNotIn(selected_name, result.stdout + result.stderr)
                self.assertNotIn(payload, result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_validates_every_settings_occurrence(self) -> None:
        bypass = '{"env":{"CLAUDE_CODE_USE_BEDROCK":"1"}}'

        result, log = self.run_launcher(
            "launch", "--settings", '{"custom":true}', "--settings", bypass
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CLAUDE_CODE_USE_BEDROCK", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_rejects_missing_or_empty_settings_option_values(self) -> None:
        for arguments in (("--settings",), ("--settings=",)):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("launch", *arguments)

                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("--settings", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_refuses_invalid_inline_settings_without_echoing_them(self) -> None:
        for payload in ("{not-json", "null", "42", '["not", "an", "object"]'):
            with self.subTest(payload=payload):
                result, log = self.run_launcher("launch", "--settings", payload)

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("valid JSON object or a readable settings file", result.stderr)
                self.assertNotIn(payload, result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_refuses_invalid_selected_settings_files(self) -> None:
        selected_name = "selected-settings-OCX_PATH_SECRET.json"
        for payload in ("", "{not-json", "null", '["not", "an", "object"]'):
            with self.subTest(payload=payload):
                result, log = self.run_launcher(
                    "launch", "--settings", selected_name,
                    selected_settings_raw=payload,
                    selected_settings_name=selected_name,
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("--settings", result.stderr)
                self.assertNotIn(selected_name, result.stdout + result.stderr)
                self.assertNotIn("{not-json", result.stdout + result.stderr)
                self.assertNotIn('["not", "an", "object"]', result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_refuses_unavailable_selected_settings_files(self) -> None:
        selected_name = "selected-settings-OCX_PATH_SECRET.json"
        cases = (
            (("--settings", "missing-settings-OCX_PATH_SECRET.json"), {}),
            (
                ("--settings", "OCX_PATH_SECRET"),
                {
                    "selected_settings_name": "OCX_PATH_SECRET",
                    "selected_settings_directory": True,
                },
            ),
            (
                ("--settings", selected_name),
                {
                    "selected_settings_raw": "{}",
                    "selected_settings_name": selected_name,
                    "selected_settings_mode": 0,
                },
            ),
        )
        for arguments, fixture in cases:
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("launch", *arguments, **fixture)

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("--settings", result.stderr)
                self.assertNotIn("OCX_PATH_SECRET", result.stdout + result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_selected_settings_path_is_redacted_when_the_file_disappears_before_open(self) -> None:
        selected_name = "selected-settings-OCX_PATH_SECRET.json"

        result, log = self.run_launcher(
            "launch", "--settings", selected_name,
            selected_settings_raw="{}",
            selected_settings_name=selected_name,
            remove_selected_settings_before_open=True,
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("could not be checked", result.stderr)
        self.assertNotIn("OCX_PATH_SECRET", result.stdout + result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_ordinary_launch_accepts_a_scalar_shaped_settings_filename(self) -> None:
        result, log = self.run_launcher(
            "launch", "--settings", "true",
            selected_settings_raw='{"custom":true}', selected_settings_name="true",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertExactTracedOcxRoute(log, "claude", "--settings", "true")

    def test_existing_persistent_settings_must_be_json_objects(self) -> None:
        for payload in ("", "null", "42", '[]'):
            with self.subTest(payload=payload):
                result, log = self.run_launcher("launch", global_settings_raw=payload)

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("could not be checked", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

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
                # ... and it must not have started or contacted a gateway to find that out. CONTACT
                # is genuinely covered now: the curl stub traces every direct HTTP call into the
                # same log as `<curl>...`, and assertOnlyReadOnlyOcxRoutes admits no such line, so
                # this asserts the claim the comment makes rather than only which ocx verbs ran.
                # (It used to say "contacted" while classifying nothing but ocx invocations, and the
                # three /healthz and /v1/models call sites were invisible to it.)
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

    # --- selected-model admission (seed agentic-sdlc-fa32) ------------------------------------
    #
    # The gateway's router does not fail closed on a provider prefix it does not serve. It computes
    # the prefix, fails to match it against the configured providers, DISCARDS that failure, and
    # forwards the caller's model string verbatim to whichever provider is DEFAULT, tagged
    # `routeKind: "default-provider"` -- so the request is attempted and billed against the wrong
    # account while attribution records the wrong provider. Three such rows were in this host's own
    # gateway store inside seven days. The launcher cannot fix the router; what it can do is refuse
    # to hand it an id it will misroute, and these tests are what keep that refusal honest in both
    # directions -- it must bite on an unserved prefix and must NOT bite on the legitimate routes.
    #
    # Shape copied from the real `GET /v1/models`: bare native rows, and routed rows whose id is the
    # raw `<provider>/<model>` concatenation, which for OpenRouter really does carry two slashes.
    LIVE_CATALOG = {
        "object": "list",
        "data": [
            {"id": "gpt-5.6-sol", "object": "model", "owned_by": "openai"},
            {"id": "muse/muse-spark-1.2", "object": "model", "owned_by": "muse"},
            {
                "id": "openrouter/~anthropic/claude-fable-latest",
                "object": "model",
                "owned_by": "openrouter",
            },
        ],
    }

    def test_launch_refuses_a_model_whose_provider_the_gateway_does_not_serve(self) -> None:
        result, log = self.run_launcher(
            "launch",
            "--model",
            "zzz-totally-unconfigured-provider/some-model",
            catalog_json=self.LIVE_CATALOG,
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        # Name the prefix, or the operator cannot tell which of their ids was wrong.
        self.assertIn("zzz-totally-unconfigured-provider", result.stderr)
        self.assertIn("serves no provider of that name", result.stderr)
        # Say what would have happened, so the refusal reads as a billing fact and not as pedantry.
        self.assertIn("default-provider", result.stderr)
        # The assertion that actually matters: exit 3 with a launched session is not a refusal.
        self.assertNotIn("<ocx><claude>", log.read_text())

    def test_launch_accepts_a_model_whose_provider_the_gateway_serves(self) -> None:
        # POSITIVE CONTROL for the test above. Without this, a check that refused EVERY namespaced
        # id would pass the refusal test and break every routed model in the bundle.
        result, log = self.run_launcher(
            "launch", "--model", "muse/muse-spark-1.2", catalog_json=self.LIVE_CATALOG
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_launch_accepts_the_two_slash_routed_id_the_catalog_really_serves(self) -> None:
        # `/v1/models` emits `<provider>/<native-id>` unencoded, and OpenRouter's own native ids
        # contain a slash, so the id a caller copies out of the catalog has TWO. A check that split
        # on the last slash, or that required exactly one, would refuse the catalog's own rows.
        result, log = self.run_launcher(
            "launch",
            "--model",
            "openrouter/~anthropic/claude-fable-latest",
            catalog_json=self.LIVE_CATALOG,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_launch_never_refuses_a_bare_model_id_and_needs_no_catalog_to_allow_it(self) -> None:
        # The legitimate flow this check must not break. A bare `claude-*` id is the native
        # Anthropic passthrough this whole route exists to preserve, it is answered on the
        # operator's own subscription, and a live catalog need carry no `claude*` row at all --
        # this host's does not. No catalog fixture is passed, so the id is admitted without one:
        # a bare id is decided before the catalog is ever read.
        result, log = self.run_launcher("launch", "--model", "claude-sonnet-5")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_launch_does_not_refuse_a_routing_profile_selection(self) -> None:
        # `policy/<id>` is resolved by the router BEFORE the provider-prefix branch, and an unknown
        # profile already fails closed upstream, so this check has nothing to add and no business
        # refusing it. `policy` is not a provider and never appears in the catalog, so a check that
        # only asked "is the prefix a live provider" would refuse a working selection.
        result, log = self.run_launcher(
            "launch", "--model", "policy/cheap-first", catalog_json=self.LIVE_CATALOG
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_an_uncheckable_catalog_refuses_a_namespaced_model_instead_of_launching_it(self) -> None:
        # Fail-open is the defect under repair, so it must not be reintroduced as a degrade: with no
        # catalog fixture the stub curl fails, nothing was checked, and a selection that could not
        # be verified stops the launch rather than passing as served. Same rule the unverifiable
        # `--settings` document already follows.
        result, log = self.run_launcher("launch", "--model", "muse/muse-spark-1.2")

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("could not be read", result.stderr)
        self.assertNotIn("<ocx><claude>", log.read_text())

    def test_launch_refuses_a_configured_but_unpublished_provider_and_names_the_publish_step(self) -> None:
        # Configuration drift reaches the SAME misroute as a typo, and the launcher already warns
        # about it after a provider mutation -- but nothing stopped a dispatch to it. The remedy
        # differs from a typo's, so the refusal distinguishes the two rather than printing one
        # sentence for both.
        result, log = self.run_launcher(
            "launch",
            "--model",
            "openrouter/some-model",
            catalog_json={"object": "list", "data": [{"id": "gpt-5.6-sol"}]},
            provider_list_json={
                "configured": [
                    {"name": "openai", "isDefault": True},
                    {"name": "openrouter", "isDefault": False},
                ]
            },
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CONFIGURED but is not in the running gateway's catalog", result.stderr)
        self.assertIn("ocx sync", result.stderr)
        self.assertNotIn("<ocx><claude>", log.read_text())

    def test_launch_accepts_an_explicit_namespace_on_the_default_provider(self) -> None:
        # REGRESSION, and it was a real one: the default provider serves BARE ids, so it never
        # appears as a `<name>/` row in the catalog, while the router still matches it by name and
        # routes there EXPLICITLY rather than through the fallthrough. An earlier draft of this check
        # therefore refused `openai/gpt-5.5` on a host whose default IS openai -- a working
        # selection, caught by replaying the rule against this host's real live catalog rather than
        # against the fixture. The catalog below deliberately carries no `openai/` row.
        result, log = self.run_launcher(
            "launch",
            "--model",
            "openai/gpt-5.5",
            catalog_json={"object": "list", "data": [{"id": "gpt-5.6-sol"}]},
            provider_list_json={"configured": [{"name": "openai", "isDefault": True}]},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_a_leading_slash_model_id_is_left_to_the_router(self) -> None:
        # The router guards its prefix branch on `slash > 0`, so `/foo` never reaches the prefix test
        # upstream. Claiming jurisdiction over a shape the router does not treat as namespaced would
        # be this check inventing a refusal rather than mirroring one.
        #
        # WHAT THIS TEST DOES AND DOES NOT PROVE, because mutation testing showed the difference.
        # Deleting the launcher's explicit leading-slash guard does NOT make this test fail: without
        # it the prefix is the empty string, and `grep -qxF ""` matches every line, so the id is
        # admitted by accident instead of by intent. No test can isolate that guard, because both
        # paths reach the same verdict. This pins the BEHAVIOUR -- a leading-slash id is not refused
        # -- which is a real regression pin if someone later makes it refuse. It is not evidence that
        # the guard is what produces that behaviour. The guard is kept anyway so the outcome stops
        # depending on an empty grep pattern matching everything, which a later edit could silently
        # turn into a refusal.
        result, log = self.run_launcher(
            "launch", "--model", "/some-model", catalog_json=self.LIVE_CATALOG
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_the_equals_spelling_of_the_model_argument_is_checked_too(self) -> None:
        # `--model=x` and `--model x` are one selection with two spellings; checking only the
        # separated form leaves a bypass that looks like a working launch.
        result, log = self.run_launcher(
            "launch", "--model=zzz-unserved-provider/some-model", catalog_json=self.LIVE_CATALOG
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("zzz-unserved-provider", result.stderr)
        self.assertNotIn("<ocx><claude>", log.read_text())

    def test_ultracode_inherits_the_selected_model_refusal(self) -> None:
        # launch-ultracode reaches the gateway through cmd_launch, so the check must cover it
        # without a second copy. It also arrives carrying its own `--settings`, which must not
        # shadow the `--model` scan.
        result, log = self.run_launcher(
            "launch-ultracode",
            "--model",
            "zzz-unserved-provider/some-model",
            catalog_json=self.LIVE_CATALOG,
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("zzz-unserved-provider", result.stderr)
        self.assertNotIn("<ocx><claude>", log.read_text())

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
                result, log = self.run_launcher(
                    "launch", global_settings={"env": {"ANTHROPIC_BASE_URL": value}}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                # Exit 0 alone is not acceptance. A regression that refused the settings channel,
                # or short-circuited before `ocx claude`, would still exit 0 on some paths, so the
                # trace has to show the launch actually REACHED the wrapped tool.
                self.assertIn("<ocx><claude>", log.read_text())

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
        result, log = self.run_launcher("launch", parent_env={"ANTHROPIC_BASE_URL": ""})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

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

    def test_a_json_false_in_a_settings_env_slot_is_read_as_a_value_not_as_absent(self) -> None:
        # jq's `//` is false-OR-null, not null-coalescing, so `$env[.] // ""` read a JSON LITERAL
        # `false` as ABSENT and reported the whole document CLEAN. Measured against the pre-fix
        # program: `{"env":{"ANTHROPIC_BASE_URL":false}}` and
        # `{"env":{"ANTHROPIC_BEDROCK_BASE_URL":false}}` both passed, while the identical
        # `"https://evil.example"` refused -- a type confusion in a security guard.
        #
        # It mattered because Claude Code does not drop or reject a non-string here. MEASURED on
        # 2026-08-11 against 2.1.227: its settings-env filter chain passes values through untouched
        # and then `Object.assign(process.env, ...)` STRINGIFIES them, so a JSON `false` arrives in
        # the session, and in every child, as the string "false". A probe with a blocking
        # UserPromptSubmit hook dumped `AWS_BEARER_TOKEN_BEDROCK=false` and
        # `ANTHROPIC_BEDROCK_BASE_URL=false` out of the child environment: SET and non-empty, which
        # is exactly the condition an endpoint slot refuses on. Only the STRING "false" was pinned
        # before (see the disabled-switch test below); the JSON literal was untested.
        for name in (
            "AWS_BEARER_TOKEN_BEDROCK",
            "ANTHROPIC_BEDROCK_BASE_URL",
            "ANTHROPIC_VERTEX_BASE_URL",
            "ANTHROPIC_AWS_BASE_URL",
            "ANTHROPIC_GOOGLE_CLOUD_BASE_URL",
            "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
        ):
            with self.subTest(slot=name):
                result, log = self.run_launcher(
                    "launch", global_settings={"env": {name: False}}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertIn("settings.json", result.stderr)
                self.assertNotIn("routed at", result.stdout)
                self.assertOnlyReadOnlyOcxRoutes(log)

        with self.subTest(slot="ANTHROPIC_BASE_URL"):
            result, log = self.run_launcher(
                "launch", global_settings={"env": {"ANTHROPIC_BASE_URL": False}}
            )

            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("ANTHROPIC_BASE_URL", result.stderr)
            self.assertIn("settings.json", result.stderr)
            self.assertNotIn("routed at", result.stdout)
            self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_json_boolean_switch_keeps_the_truthiness_rule_it_always_had(self) -> None:
        # The null-only fallback must not turn the BOOLEAN class into a presence check. There a
        # `false` legitimately means off -- the client's own truthiness reads the stringified
        # "false" as disabled -- so it must still launch, while `true` must still refuse. This is
        # the pair that proves the fix is a type correction and not a widened refusal.
        result, log = self.run_launcher(
            "launch", global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": False}}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

        result, log = self.run_launcher(
            "launch", global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": True}}
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CLAUDE_CODE_USE_BEDROCK", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_disabled_provider_switch_does_not_refuse_a_working_launch(self) -> None:
        # Measured: with CLAUDE_CODE_USE_BEDROCK=0 the traffic still went to ANTHROPIC_BASE_URL, so
        # refusing on presence alone stopped a launch that works -- and `=0` is exactly how an
        # operator disables a switch inherited from a profile or a wrapper. Both channels must agree
        # on that, which they did not while one tested emptiness and the other tested key presence.
        for value in ("0", "", "false", "FALSE", " false "):
            with self.subTest(value=value, channel="exported"):
                result, log = self.run_launcher(
                    "launch", parent_env={"CLAUDE_CODE_USE_BEDROCK": value}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<ocx><claude>", log.read_text())
            with self.subTest(value=value, channel="settings"):
                result, log = self.run_launcher(
                    "launch", global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": value}}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<ocx><claude>", log.read_text())

    def test_an_enabled_provider_switch_still_refuses_in_both_channels(self) -> None:
        # Truthiness must not become a bypass: anything that is not "", "0" or "false" is enabled.
        for value in ("1", "true", "TRUE", "on"):
            with self.subTest(value=value, channel="exported"):
                result, log = self.run_launcher(
                    "launch", parent_env={"CLAUDE_CODE_USE_VERTEX": value}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("CLAUDE_CODE_USE_VERTEX", result.stderr)
                # Exit 3 alone does not prove the refusal landed BEFORE the wrapped tool ran.
                self.assertOnlyReadOnlyOcxRoutes(log)
            with self.subTest(value=value, channel="settings"):
                result, log = self.run_launcher(
                    "launch", global_settings={"env": {"CLAUDE_CODE_USE_VERTEX": value}}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("CLAUDE_CODE_USE_VERTEX", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_an_empty_endpoint_slot_is_not_read_as_a_configured_route(self) -> None:
        # The value-based half of the same consistency: an empty endpoint names no destination, so
        # it must not refuse. The settings channel used to refuse it on key presence alone.
        result, log = self.run_launcher("launch", parent_env={"ANTHROPIC_BEDROCK_BASE_URL": ""})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

        result, log = self.run_launcher(
            "launch", global_settings={"env": {"ANTHROPIC_BEDROCK_BASE_URL": ""}}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    # --- cloud-provider-shaped model-slot overrides (executed 2026-08-20) -------------------
    #
    # THE GAP: with CLAUDE_CODE_USE_BEDROCK unset -- so every switch check above passed -- and
    # ANTHROPIC_DEFAULT_SONNET_MODEL exporting `global.anthropic.claude-sonnet-5[1m]`, `launch`
    # PROCEEDED and the session 400d at the Codex upstream, because the gateway does not read a
    # provider-shaped id as native Anthropic passthrough and fell through to the DEFAULT provider.
    # The refusal set covered switches, endpoints, base URLs and Console keys, and not this.
    MODEL_SLOT_OVERRIDES = (
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        # RESIDUAL from the 8b1e1ba fix, now closed: `skills/model-tier-rightsizing/references/`
        # `workflow-prompt-budget.md` records `effectiveModelEnv()` injecting these two into the
        # SAME tier-slot set as the original four, so a cloud-shaped id in either is the identical
        # hazard -- it re-points a whole model family without touching any switch above.
        "ANTHROPIC_DEFAULT_FABLE_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL",
        "ANTHROPIC_MODEL",
    )
    # The shape families the refusal knows: region-prefixed Bedrock inference profiles, the bare
    # Bedrock publisher form, and the two Vertex spellings.
    CLOUD_SHAPED_MODEL_IDS = (
        "global.anthropic.claude-sonnet-5[1m]",
        "us.anthropic.claude-opus-4-5-v1:0",
        "eu.anthropic.claude-haiku-4-5",
        "anthropic.claude-3-5-haiku-20241022-v1:0",
        "claude-sonnet-4@20250514",
        "publishers/anthropic/models/claude-opus-4",
    )
    # THE POSITIVE CONTROL, and the reason this is a shape test rather than a presence test: these
    # are the ordinary values of the same six variables. A plain alias is what the native half of
    # this route serves, and a gateway id in the small-fast slot is a legitimate use of the routed
    # half, so refusing either would break the launch this check exists to protect.
    PLAIN_MODEL_IDS = (
        "claude-sonnet-5",
        "claude-haiku-4-5",
        "claude-3-7-sonnet-latest",
        "muse/muse-spark-1.2",
    )

    def test_launch_refuses_a_cloud_shaped_model_slot_exported_in_this_shell(self) -> None:
        # Every one of the six slots, on the id that was actually measured failing.
        for name in self.MODEL_SLOT_OVERRIDES:
            value = "global.anthropic.claude-sonnet-5[1m]"
            with self.subTest(variable=name):
                result, log = self.run_launcher("launch", parent_env={name: value})

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                # A model id is not a credential, so unlike a base URL the value IS named -- with
                # six slots to choose from, withholding it leaves the operator guessing.
                self.assertIn(value, result.stderr)
                # The refusal has to say WHY it is not a warning: the slot re-points an upstream.
                self.assertIn("DEFAULT provider", result.stderr)
                self.assertNotIn("routed at", result.stdout)
                # And it must land before anything is started or contacted.
                self.assertOnlyReadOnlyOcxRoutes(log)

        # Every shape family, on one slot, so a pattern narrowed to the Bedrock case fails here.
        for value in self.CLOUD_SHAPED_MODEL_IDS:
            with self.subTest(value=value):
                result, log = self.run_launcher(
                    "launch", parent_env={"ANTHROPIC_DEFAULT_SONNET_MODEL": value}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_DEFAULT_SONNET_MODEL", result.stderr)
                self.assertIn(value, result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

        # IN-TEST POSITIVE CONTROL. Exit 3 on six fixtures proves nothing about a refusal that
        # simply refuses everything, so the ordinary values must still LAUNCH -- and reaching
        # `ocx claude` in the trace is what distinguishes that from an exit-0 short circuit.
        for name in self.MODEL_SLOT_OVERRIDES:
            with self.subTest(variable=name, control="plain alias"):
                result, log = self.run_launcher(
                    "launch", parent_env={name: "claude-sonnet-5"}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<ocx><claude>", log.read_text())
        for value in self.PLAIN_MODEL_IDS:
            with self.subTest(value=value, control="ordinary id"):
                result, log = self.run_launcher(
                    "launch", parent_env={"ANTHROPIC_SMALL_FAST_MODEL": value}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<ocx><claude>", log.read_text())

    def test_launch_refuses_a_cloud_shaped_model_slot_in_a_settings_env_block(self) -> None:
        # The sibling channel every other refusal in this section covers twice: a settings `env`
        # block is read on every launch and survives a clean shell, so a slot that refuses from the
        # shell and passes silently from the file is the exact drift the shared jq program prevents.
        for name in self.MODEL_SLOT_OVERRIDES:
            with self.subTest(variable=name, channel="global settings"):
                result, log = self.run_launcher(
                    "launch",
                    global_settings={"env": {name: "us.anthropic.claude-opus-4-5-v1:0"}},
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertIn("settings.json", result.stderr)
                self.assertIn("DEFAULT provider", result.stderr)
                self.assertNotIn("routed at", result.stdout)
                self.assertOnlyReadOnlyOcxRoutes(log)

        for document in ("project_settings", "project_settings_local"):
            with self.subTest(channel=document):
                result, log = self.run_launcher(
                    "launch",
                    **{document: {"env": {
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-sonnet-4@20250514"
                    }}},
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_DEFAULT_HAIKU_MODEL", result.stderr)
                # The refusal names the document it actually read, not the global one.
                self.assertIn(f"{self.project}/.claude/settings", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

        with self.subTest(channel="explicit --settings"):
            # The third settings source has its own refusal text, so it needs its own arm rather
            # than the generic "routes Claude Code to a cloud provider" fallback, which is not what
            # a model-slot id does.
            result, log = self.run_launcher(
                "launch",
                "--settings",
                '{"env":{"ANTHROPIC_SMALL_FAST_MODEL":"anthropic.claude-3-5-haiku-20241022-v1:0"}}',
            )

            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("ANTHROPIC_SMALL_FAST_MODEL", result.stderr)
            self.assertIn("DEFAULT provider", result.stderr)
            self.assertOnlyReadOnlyOcxRoutes(log)

        # IN-TEST POSITIVE CONTROL for the same channel.
        result, log = self.run_launcher(
            "launch", global_settings={"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-5"}}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    # RESIDUAL (1) from the 8b1e1ba fix: every alternative in $cloud_provider_model_id_pattern
    # anchors on `^` or `$`, so a stray leading or trailing space around an otherwise cloud-shaped
    # id slipped past both engines. MEASURED before the fix:
    # `ANTHROPIC_DEFAULT_SONNET_MODEL=' global.anthropic.claude-sonnet-5[1m]'` (one leading space)
    # launched clean.
    PADDED_CLOUD_SHAPED_MODEL_IDS = (
        " global.anthropic.claude-sonnet-5[1m]",
        "global.anthropic.claude-sonnet-5[1m] ",
        "  us.anthropic.claude-opus-4-5-v1:0  ",
        "\tanthropic.claude-3-5-haiku-20241022-v1:0\t",
        "claude-sonnet-5@20250101 ",
    )

    def test_launch_refuses_a_cloud_shaped_model_slot_padded_with_whitespace(self) -> None:
        # Both engines -- bash `=~` for the exported channel, jq's `test()` for the settings
        # channel -- must trim before they test the shape, or the same padded value refuses from
        # one channel and passes silently from the other exactly the way the two channels drifted
        # apart once already (see the "ONE list per class" comment above model_slot_overrides).
        for value in self.PADDED_CLOUD_SHAPED_MODEL_IDS:
            with self.subTest(channel="exported", value=repr(value)):
                result, log = self.run_launcher(
                    "launch", parent_env={"ANTHROPIC_DEFAULT_SONNET_MODEL": value}
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_DEFAULT_SONNET_MODEL", result.stderr)
                self.assertIn("DEFAULT provider", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

            with self.subTest(channel="global settings", value=repr(value)):
                result, log = self.run_launcher(
                    "launch",
                    global_settings={"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": value}},
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_DEFAULT_SONNET_MODEL", result.stderr)
                self.assertIn("DEFAULT provider", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

        # POSITIVE CONTROL: the same padding around an ORDINARY alias must not become a false
        # refusal. Trimming exists to widen the SHAPE match, not to introduce a side effect that
        # starts refusing a padded plain value this route never refused before.
        for value in (" claude-sonnet-5", "claude-sonnet-5 ", "  claude-sonnet-5  "):
            with self.subTest(control="padded plain alias", channel="exported", value=repr(value)):
                result, log = self.run_launcher(
                    "launch", parent_env={"ANTHROPIC_DEFAULT_SONNET_MODEL": value}
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<ocx><claude>", log.read_text())

        result, log = self.run_launcher(
            "launch",
            global_settings={"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "  claude-sonnet-5  "}},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

    def test_status_reports_a_cloud_shaped_model_slot_instead_of_ok(self) -> None:
        # `status` and `launch` read the same shell. A status that printed `ok` on an environment
        # `launch` refuses would be the reassurance-about-an-unchecked-surface defect this section
        # has already been fixed for once.
        result, _ = self.run_launcher(
            "status",
            parent_env={"ANTHROPIC_DEFAULT_OPUS_MODEL": "global.anthropic.claude-opus-4-5"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MISROUTED", result.stdout)
        self.assertIn("ANTHROPIC_DEFAULT_OPUS_MODEL", result.stdout)
        self.assertIn("global.anthropic.claude-opus-4-5", result.stdout)
        self.assertNotIn("nothing exported in this shell", result.stdout)

        control, _ = self.run_launcher(
            "status", parent_env={"ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-5"}
        )
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertNotIn("MISROUTED", control.stdout)
        self.assertIn("nothing exported in this shell", control.stdout)

    def test_a_dangling_settings_symlink_is_treated_as_no_settings_at_all(self) -> None:
        # Claude Code reads this path and treats ENOENT as no settings, so a dotfile symlink whose
        # target moved carries no key that could outrank the gateway. Admitting it as absent matches
        # the client; failing closed there would hard-stop a working launch over a broken dotfile.
        result, log = self.run_launcher("launch")
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
        # Both launches share one trace log, so a bare `assertIn` here would be satisfied by the
        # FIRST launch alone and would say nothing about the dangling symlink. Counting is what
        # makes the second launch's acceptance load-bearing.
        self.assertEqual(log.read_text().count("<ocx><claude>"), 2)

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
        result, log = self.run_launcher(
            "launch", project_settings_local={"env": {"CLAUDE_CODE_USE_VERTEX": "1"}}
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn(f"{self.project}/.claude/settings.local.json", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_clean_project_document_does_not_refuse(self) -> None:
        # The project documents are ordinary files that usually carry permissions and hooks. Only a
        # routing key, an apiKeyHelper or a Console-shaped value may stop a launch.
        result, log = self.run_launcher(
            "launch",
            project_settings={"permissions": {"allow": ["Bash"]}, "env": {"FOO": "bar"}},
            project_settings_local={"env": {"CLAUDE_CODE_USE_BEDROCK": "0"}},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<ocx><claude>", log.read_text())

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
        self.assertIn("Claude.ai cloud connectors are off by default", result.stdout)
        self.assertIn("ENABLE_CLAUDEAI_MCP_SERVERS=true", result.stdout)
        self.assertIn("--settings <file-or-json>", result.stdout)
        self.assertIn("every occurrence for route-bypassing settings", result.stdout)
        self.assertIn("bytes and path are never printed", result.stdout)
        # The refusal list is the operator-facing contract for this route, so a refusal the code
        # performs and the help omits is a documentation defect, not a cosmetic gap. Minor residual
        # from the 8b1e1ba fix, closed: this one-line usage() mention had no dedicated assertion at
        # all, and it now also states the trim behaviour rather than just the six variable names.
        for name in self.MODEL_SLOT_OVERRIDES:
            self.assertIn(name, result.stdout)
        self.assertIn("does not defeat this check", result.stdout)

    def test_launch_help_calls_the_unrecognized_model_line_cosmetic_and_bounds_the_observe_log(
        self,
    ) -> None:
        # Two findings from the 2026-08-20 retest, both of which cost a careful reviewer a false
        # negative. The `[claude-code:unrecognized_model]` line reads as a routing failure and is
        # not one -- the same turn was receipt-verified as reaching its provider -- and a single
        # empty `ocx observe logs` query was read as proof that nothing routed, when that log is a
        # bounded rolling window in which absence means unknown.
        result, _ = self.run_launcher("launch", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[claude-code:unrecognized_model]", result.stdout)
        self.assertIn("cosmetic", result.stdout)
        self.assertIn("NOT a routing failure", result.stdout)
        self.assertIn("ocx observe logs --jsonl", result.stdout)
        self.assertIn("rolling window", result.stdout)
        self.assertIn("UNKNOWN", result.stdout)
        self.assertIn("receipt", result.stdout)

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

    def test_status_lists_a_document_once_when_home_is_a_second_spelling_of_the_launch_directory(
        self,
    ) -> None:
        # The case above only ever exercised ONE spelling of the home directory, which is the one
        # spelling a string compare already collapses. Both spellings below name the same directory
        # as the launch directory by a different route -- a trailing slash, and a symlink -- and a
        # dedupe keyed on the raw string listed the same file twice for each. Neither needs an
        # exotic host: Silverblue/CoreOS puts `/home` behind a symlink to `/var/home`, a macOS home
        # can sit under a symlinked volume, and any profile writing `HOME="$prefix/"` produces the
        # slash.
        #
        # `.claude` is deliberately never created. An absent document must still be listed exactly
        # ONCE rather than dropped, because `status` names every `checked:` path whether or not the
        # file is there -- so a fix that canonicalized only documents that exist would leave the
        # duplicate in place for the state a fresh machine is actually in.
        self.run_launcher("status")
        self.home.mkdir(parents=True, exist_ok=True)
        through_a_symlink = self.home.parent / "home-through-a-symlink"
        through_a_symlink.symlink_to(self.home, target_is_directory=True)

        for spelling in (f"{self.home}/", str(through_a_symlink)):
            with self.subTest(home=spelling):
                result = subprocess.run(
                    [BASH, str(SCRIPT), "status"],
                    text=True, capture_output=True, check=False,
                    env={**self.launch_env, "HOME": spelling},
                    cwd=str(self.home),
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                listed = [
                    line.split("checked: ", 1)[1].strip()
                    for line in result.stdout.splitlines()
                    if "checked: " in line
                ]
                self.assertEqual(
                    [path for path in listed if path.endswith("/.claude/settings.json")],
                    [f"{self.home}/.claude/settings.json"],
                    listed,
                )
                # Listed exactly once, and still LISTED: dropping an absent document would satisfy
                # a naive uniqueness check while removing a path `status` claims to have checked.
                self.assertEqual(sorted(listed), sorted(set(listed)), listed)
                self.assertIn(f"{self.home}/.claude/settings.local.json", listed)

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

    def test_launch_disables_claude_ai_connectors_unless_the_operator_opts_in(self) -> None:
        default_run, _ = self.run_launcher("launch")
        self.assertEqual(default_run.returncode, 0, default_run.stderr)
        self.assertIn("ENABLE_CLAUDEAI_MCP_SERVERS=false", self.env_log.read_text())

        chosen, _ = self.run_launcher(
            "launch", parent_env={"ENABLE_CLAUDEAI_MCP_SERVERS": "true"}
        )
        self.assertEqual(chosen.returncode, 0, chosen.stderr)
        self.assertIn("ENABLE_CLAUDEAI_MCP_SERVERS=true", self.env_log.read_text())

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

    def test_yolo_routes_keep_gateway_and_billing_refusals_before_contact(self) -> None:
        secret = "sk-ant-api03-YOLOTESTSENTINEL"
        for route in ("launch", "launch-ultracode"):
            with self.subTest(route=route, refusal="settings-route"):
                result, log = self.run_launcher(
                    route,
                    "--yolo",
                    global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}},
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("CLAUDE_CODE_USE_BEDROCK", result.stderr)
                self.assertNotIn("permissions: BYPASSED", result.stdout)
                self.assertOnlyReadOnlyOcxRoutes(log)

            with self.subTest(route=route, refusal="console-key"):
                result, log = self.run_launcher(
                    route,
                    "--yolo",
                    parent_env={"ANTHROPIC_API_KEY": secret},
                )

                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_API_KEY", result.stderr)
                self.assertIn("credits", result.stderr)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertNotIn("permissions: BYPASSED", result.stdout)
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
        # A rename can only be caught by reading the config, so this is one of the two routes that
        # legitimately classifies before refusing. Named here rather than admitted for everyone.
        self.assertOnlyReadOnlyOcxRoutes(log, "<ocx><config><show><--json>")

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
        self.assertOnlyReadOnlyOcxRoutes(log, "<ocx><config><show><--json>")

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

    # --- the ONE admitted config-plane write: OpenRouter provider pinning ---------------
    #
    # `modelOpenRouterRouting` is the only way to pin which upstream OpenRouter serves a model
    # from: `openai-chat` composes the outbound `provider` field from configuration alone, and a
    # caller-supplied `provider` in the request body is dropped by CHAT_PASSTHROUGH_FIELDS. So the
    # general config plane being shut left NO route, and exactly this path shape is now admitted.
    #
    # EVERY REFUSAL BELOW HAS AN ADMITTED TWIN, because a refusal test alone cannot tell "the
    # wrapper checked this and declined" from "the wrapper refuses the whole shape". The twin is
    # the same call with only the refused element corrected, and it must reach the tool.

    PIN_PATH = "providers.openrouter.modelOpenRouterRouting"
    PIN_PAYLOAD = '{"openai/gpt-oss-120b":{"only":["cerebras"],"allowFallbacks":false}}'
    # The qualifying provider: upstream requires BOTH the openai-chat adapter and the canonical
    # baseUrl before it will accept a routing preference at all.
    PIN_CONFIG: dict[str, object] = {
        "providers": {
            "openrouter": {"adapter": "openai-chat", "baseUrl": "https://openrouter.ai/api/v1"},
            "wrong-adapter": {
                "adapter": "openai-responses", "baseUrl": "https://openrouter.ai/api/v1",
            },
            "wrong-base-url": {
                "adapter": "openai-chat", "baseUrl": "https://models.example.test/v1",
            },
        }
    }
    # The one read-only route this arm legitimately makes: it must read the provider config to
    # qualify the named provider's adapter and baseUrl.
    PIN_CONFIG_READ = "<ocx><config><show><--json>"

    def test_configure_admits_the_openrouter_pin_write_and_forwards_the_exact_upstream_route(
        self,
    ) -> None:
        result, log = self.run_launcher(
            "configure", "config", "set", self.PIN_PATH, self.PIN_PAYLOAD, config=self.PIN_CONFIG,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        # The EXACT upstream argv, payload byte-for-byte included. A wrapper that reformatted or
        # re-serialized the JSON would change what lands in the config file, and exit 0 plus a
        # printed notice cannot tell that apart from a faithful forward.
        self.assertExactTracedOcxRoute(log, "config", "set", self.PIN_PATH, self.PIN_PAYLOAD)
        # AND NOTHING ELSE RAN. This is what holds "prints the publish step, never runs it" to
        # account: an `ocx sync` or a restart forwarded here would be an unauthorized outward
        # effect, and `also_admitted` can only widen by exact line, so neither can hide.
        self.assertOnlyReadOnlyOcxRoutes(
            log,
            self.PIN_CONFIG_READ,
            self.traced_ocx_route("config", "set", self.PIN_PATH, self.PIN_PAYLOAD),
        )
        self.assertIn("NOT LIVE YET", result.stdout)
        self.assertIn("ccodex restart", result.stdout)
        # NEITHER HALF of the provider notice, because both are false instructions here. The
        # provider arms print `exec -- ocx sync` as a command to run and explain that the provider
        # is not in the routing table so requests fall through to `default-provider`; this write is
        # to an ALREADY-live provider, and the value is read from the gateway's own provider config
        # rather than republished into ~/.codex. Matching the command form, not the bare words, so
        # the notice can still explain in prose that there is no sync step.
        self.assertNotIn("exec -- ocx sync", result.stdout)
        self.assertNotIn("default-provider", result.stdout)

    def test_configure_admits_the_openrouter_pin_unset(self) -> None:
        result, log = self.run_launcher(
            "configure", "config", "unset", self.PIN_PATH, config=self.PIN_CONFIG,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertExactTracedOcxRoute(log, "config", "unset", self.PIN_PATH)
        self.assertOnlyReadOnlyOcxRoutes(
            log,
            self.PIN_CONFIG_READ,
            self.traced_ocx_route("config", "unset", self.PIN_PATH),
        )
        self.assertIn("NOT LIVE YET", result.stdout)
        self.assertIn("ccodex restart", result.stdout)

    def test_a_failed_pin_write_prints_no_publish_notice(self) -> None:
        # Same rule as the provider arms: "restart to publish this" over a write that did not land
        # is a false instruction. Without this, the notice assertions above pass with the whole
        # passthrough gutted.
        result, _ = self.run_launcher(
            "configure", "config", "set", self.PIN_PATH, self.PIN_PAYLOAD,
            config=self.PIN_CONFIG, ocx_exit=1,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("NOT LIVE YET", result.stdout)

    def test_a_config_path_that_is_not_the_pin_path_is_still_refused_as_unbounded(self) -> None:
        # THE TWIN of the admitted test above: only the PATH differs. Each of these is a key the
        # pinning route must not have opened -- a credential, a base URL, the provider's whole
        # object, a sibling routing field that is NOT the exact-model map, and an unrelated
        # top-level key.
        for path in (
            "providers.openrouter.apiKey",
            "providers.openrouter.baseUrl",
            "providers.openrouter",
            "providers.openrouter.openRouterRouting",
            "codexAccountPriorities",
        ):
            for action in ("set", "unset"):
                with self.subTest(path=path, action=action):
                    arguments = ["configure", "config", action, path]
                    if action == "set":
                        arguments.append(self.PIN_PAYLOAD)
                    result, log = self.run_launcher(*arguments, config=self.PIN_CONFIG)

                    self.assertEqual(result.returncode, 3)
                    # Not even the config READ: a non-pinning path is refused on its shape alone,
                    # before anything about the provider is looked up.
                    self.assertOnlyReadOnlyOcxRoutes(log)
                    self.assertIn("unbounded-route", result.stderr)

    def test_a_wildcard_or_deeper_provider_segment_is_refused(self) -> None:
        # The admission is one provider, named exactly. A glob would reach every provider through
        # one write, and a deeper path would reach a key inside the routing map.
        for path in (
            "providers.*.modelOpenRouterRouting",
            "providers.open?outer.modelOpenRouterRouting",
            "providers.openrouter.extra.modelOpenRouterRouting",
            "providers..modelOpenRouterRouting",
            "providers.__proto__.modelOpenRouterRouting",
            "providers.-openrouter.modelOpenRouterRouting",
        ):
            with self.subTest(path=path):
                result, log = self.run_launcher(
                    "configure", "config", "set", path, self.PIN_PAYLOAD, config=self.PIN_CONFIG,
                )

                self.assertEqual(result.returncode, 3)
                self.assertIn("provider-name", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_provider_absent_from_the_config_is_refused_by_exact_spelling(self) -> None:
        # Upstream resolves this path's parent as a LITERAL object key, so a case-folded match
        # would admit a route that then fails inside the tool -- which reads as this wrapper
        # having approved something broken. `OpenRouter` is the positive control's own name in a
        # different case, so this pair also pins the case sensitivity.
        for provider in ("nosuch-provider", "OpenRouter"):
            with self.subTest(provider=provider):
                result, log = self.run_launcher(
                    "configure", "config", "set",
                    f"providers.{provider}.modelOpenRouterRouting", self.PIN_PAYLOAD,
                    config=self.PIN_CONFIG,
                )

                self.assertEqual(result.returncode, 3)
                self.assertIn("provider-absent", result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log, self.PIN_CONFIG_READ)

    def test_a_provider_whose_adapter_or_base_url_disqualifies_it_is_refused(self) -> None:
        # Both are upstream preconditions (openRouterRoutingConfigError): no other adapter
        # composes OpenRouter's provider payload, and a pin sent to any other endpoint means
        # nothing. Refusing here rather than forwarding is what keeps the wrapper's approval
        # honest -- the twin above shows the same call is admitted once the provider qualifies.
        for provider, reason in (
            ("wrong-adapter", "provider-adapter"),
            ("wrong-base-url", "provider-base-url"),
        ):
            with self.subTest(provider=provider):
                result, log = self.run_launcher(
                    "configure", "config", "set",
                    f"providers.{provider}.modelOpenRouterRouting", self.PIN_PAYLOAD,
                    config=self.PIN_CONFIG,
                )

                self.assertEqual(result.returncode, 3)
                self.assertIn(reason, result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log, self.PIN_CONFIG_READ)

    def test_a_near_canonical_openrouter_base_url_is_refused(self) -> None:
        # `isCanonicalOpenRouterTarget` is narrow on purpose, and each of these would silently
        # send a pinned request somewhere the pin does not apply. The admitted spellings are the
        # positive controls in the same loop, so a check that refused everything would fail here.
        refused = (
            "http://openrouter.ai/api/v1",            # not https
            "https://openrouter.ai/API/v1",           # pathname is case-sensitive upstream
            "https://openrouter.ai/api/v2",
            "https://openrouter.ai",
            "https://openrouter.ai:8443/api/v1",      # a port that changes the origin
            # Host is a PREFIX of the canonical one, not the canonical one. Also the sentinel for
            # the never-echo assertion below, so it is spelled distinctively.
            "https://openrouter.ai.not-a-real-host.test/api/v1",
            "https://api.openrouter.ai/api/v1",
            # USERINFO, which upstream rejects via `url.username`/`url.password`. Deliberately the
            # username-only spelling: a `user:pass@` fixture is a credential-shaped string that the
            # repository's own secrets gate flags (measured -- `generic-credential-uri`), and it
            # would exercise nothing extra, since the anchored host match rejects every `...@`
            # prefix identically rather than parsing the userinfo apart.
            "https://user@openrouter.ai/api/v1",
            "https://openrouter.ai/api/v1?x=1",
            "https://openrouter.ai/api/v1#f",
            # A bare `?` parses to an EMPTY search that upstream accepts and this refuses -- a
            # deliberate narrowing, pinned so a later "simplification" cannot widen it silently.
            "https://openrouter.ai/api/v1?",
            # SCHEMELESS, and the only case the anchored host match is the sole guard for: the
            # path check alone would admit it, because a non-matching prefix leaves the string
            # untouched and `/api/v1` then matches the path anchor exactly. Upstream's `new URL()`
            # throws on a relative URL. MEASURED: dropping that anchor kills only this subTest.
            "/api/v1",
            "//openrouter.ai/api/v1",
        )
        admitted = (
            "https://openrouter.ai/api/v1",
            "https://openrouter.ai/api/v1/",          # upstream strips trailing slashes
            "https://openrouter.ai:443/api/v1",       # the default port drops out of the origin
            "HTTPS://OpenRouter.AI/api/v1",           # scheme and host fold, as URL parsing does
        )
        for base_url in refused + admitted:
            with self.subTest(base_url=base_url):
                result, log = self.run_launcher(
                    "configure", "config", "set", self.PIN_PATH, self.PIN_PAYLOAD,
                    config={"providers": {
                        "openrouter": {"adapter": "openai-chat", "baseUrl": base_url},
                    }},
                )
                if base_url in admitted:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertExactTracedOcxRoute(
                        log, "config", "set", self.PIN_PATH, self.PIN_PAYLOAD
                    )
                else:
                    self.assertEqual(result.returncode, 3)
                    self.assertIn("provider-base-url", result.stderr)
                    self.assertOnlyReadOnlyOcxRoutes(log, self.PIN_CONFIG_READ)
                    # A REFUSED BASE URL IS NEVER ECHOED, which is this launcher's standing rule
                    # because a base URL can carry userinfo. The refusal names the provider and
                    # the canonical target it needed instead.
                    #
                    # Asserted on the two DISTINCTIVE fragments above rather than on `base_url`
                    # itself: several fixtures here are substrings of the canonical
                    # `https://openrouter.ai/api/v1` that the refusal legitimately prints as
                    # guidance, so a blanket `assertNotIn(base_url, ...)` fails on the guidance
                    # rather than on an echo (measured: it failed 3 of these subTests). These two
                    # cannot appear in the guidance, so they can only appear by being echoed.
                    output = result.stdout + result.stderr
                    self.assertNotIn("not-a-real-host", output)
                    self.assertNotIn("user@", output)

    def test_a_nonconforming_pin_payload_is_refused_with_the_upstream_rule_it_broke(self) -> None:
        # Mirrors `routingPreferenceError` rule for rule, so the operator reads the message the
        # tool would have given. The conforming payloads in the same loop are the positive
        # controls: a validator that rejected everything would fail on them.
        refused = (
            ("not json at all", "payload-not-json"),
            ("[]", "must be a plain object"),
            ('"a string"', "must be a plain object"),
            ('{"m":"not an object"}', "must be a plain object"),
            ('{"m":{}}', "must define order, only, or allowFallbacks"),
            ('{"m":{"only":["groq"],"bogus":1}}', 'unknown field "bogus"'),
            ('{"m":{"only":[]}}', "1-64 provider slugs"),
            ('{"m":{"order":["groq","groq"]}}', "duplicate provider slugs"),
            ('{"m":{"only":[" groq"]}}', "nonblank trimmed provider slugs"),
            ('{"m":{"only":[7]}}', "nonblank trimmed provider slugs"),
            ('{"m":{"allowFallbacks":"false"}}', "must be a boolean"),
            ('{" m":{"only":["groq"]}}', "nonblank trimmed model ids"),
        )
        admitted = (
            '{"openai/gpt-oss-120b":{"only":["cerebras"]}}',
            '{"openai/gpt-oss-120b":{"order":["cerebras","groq"],"allowFallbacks":true}}',
            '{"a":{"allowFallbacks":false},"b":{"only":["groq"]}}',
            "{}",  # upstream accepts an empty map, so this wrapper does not invent a stricter rule
        )
        for payload, expected in refused:
            with self.subTest(payload=payload):
                result, log = self.run_launcher(
                    "configure", "config", "set", self.PIN_PATH, payload, config=self.PIN_CONFIG,
                )

                self.assertEqual(result.returncode, 3)
                self.assertIn(expected, result.stderr)
                self.assertOnlyReadOnlyOcxRoutes(log, self.PIN_CONFIG_READ)
        for payload in admitted:
            with self.subTest(payload=payload):
                result, log = self.run_launcher(
                    "configure", "config", "set", self.PIN_PATH, payload, config=self.PIN_CONFIG,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTracedOcxRoute(log, "config", "set", self.PIN_PATH, payload)

    def test_the_pin_grammar_admits_no_extra_argument(self) -> None:
        # The whole point of a narrow admission is that nothing rides in behind a valid path.
        # Upstream's own `rejectArgs` would refuse these too, but that would be the tool declining
        # a route this wrapper had already approved and forwarded.
        conforming = '{"m":{"only":["groq"]}}'
        for arguments in (
            ("config", "set", self.PIN_PATH, conforming, "--json"),
            ("config", "set", self.PIN_PATH, conforming, "extra"),
            ("config", "set", self.PIN_PATH),
            ("config", "unset", self.PIN_PATH, "--json"),
            ("config", "unset", self.PIN_PATH, conforming),
        ):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher("configure", *arguments, config=self.PIN_CONFIG)

                self.assertEqual(result.returncode, 3)
                self.assertOnlyReadOnlyOcxRoutes(log)
        # A bare `config set <path>` with no value is a usage error rather than a grammar refusal
        # in upstream's own terms, so it is checked above for exit 3 and named here for clarity:
        # the wrapper counts arguments before it looks at anything else.
        result, _ = self.run_launcher(
            "configure", "config", "set", self.PIN_PATH, config=self.PIN_CONFIG,
        )
        self.assertIn("grammar", result.stderr)

    def test_the_pin_admission_names_no_admitted_jq_route_rather_than_blaming_the_provider(
        self,
    ) -> None:
        # Same rule as `test_a_configure_mutation_names_the_tool_when_no_admitted_jq_route_runs`:
        # a missing tool is about this host's installation, not about the provider or the payload,
        # and qualifying the provider is impossible without reading the config.
        result, log = self.run_launcher(
            "configure", "config", "set", self.PIN_PATH, self.PIN_PAYLOAD,
            config=self.PIN_CONFIG, bound_jq_missing=True,
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("no admitted `jq` route runs on this host", result.stderr)
        self.assertNotIn("provider-absent", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log, self.PIN_CONFIG_READ)

    # --- agentic-sdlc-4518: the config-plane refusal explains the config plane ------------
    #
    # THE DEFECT: every configure refusal delegated to `refuse`, whose body is the ADR-0014
    # LAUNCH-route explanation. Refusing `config set` and then discussing provider-routing
    # variables, apiKeyHelper, Console keys and model slots sends the reader to inspect four
    # things that have nothing to do with the verb they typed.
    #
    # Sentinels drawn from `refuse`'s body, so this cannot pass by the text merely being reworded.
    LAUNCH_ROUTE_SENTINELS = (
        "outranks the gateway's base URL",
        "cloud-provider route is a different command",
        "saved claude.ai login stays the active credential",
        "Bedrock",
    )

    def test_the_config_plane_refusal_names_the_verb_and_drops_the_launch_route_text(self) -> None:
        for arguments, named in (
            (("config", "set", "providers.openrouter.apiKey", "v"), "ocx config set"),
            (("config", "unset", "providers.openrouter.apiKey"), "ocx config unset"),
            (("config", "import", "candidate.json", "--yes"), "ocx config import"),
            (("config", "export", "-"), "ocx config export"),
        ):
            with self.subTest(arguments=arguments):
                result, _ = self.run_launcher("configure", *arguments, config=self.PIN_CONFIG)

                self.assertEqual(result.returncode, 3)
                # The first line's shape is preserved: the reason token is read out of it.
                self.assertIn(
                    "REFUSED: opencodex configuration route refused (unbounded-route);",
                    result.stderr,
                )
                self.assertIn(named, result.stderr)
                for sentinel in self.LAUNCH_ROUTE_SENTINELS:
                    self.assertNotIn(sentinel, result.stderr)
                # And it says what IS admitted, including the one config-plane write.
                self.assertIn("provider add|edit|update|remove", result.stderr)
                self.assertIn("modelOpenRouterRouting", result.stderr)

    def test_the_launch_route_body_is_still_reachable_from_a_provider_boundary_refusal(
        self,
    ) -> None:
        # THE POSITIVE CONTROL for the test above. Without it, deleting `refuse`'s body outright
        # would satisfy every assertNotIn and the pair would prove nothing. A provider-boundary
        # refusal is the case where that text IS on topic, so it must still carry it.
        result, _ = self.run_launcher("configure", "login", "anthropic")

        self.assertEqual(result.returncode, 3)
        self.assertIn("anthropic-or-unclassifiable-provider", result.stderr)
        for sentinel in self.LAUNCH_ROUTE_SENTINELS:
            self.assertIn(sentinel, result.stderr)

    def test_the_pin_refusal_carries_no_launch_route_text_either(self) -> None:
        result, _ = self.run_launcher(
            "configure", "config", "set", self.PIN_PATH, "[]", config=self.PIN_CONFIG,
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("REFUSED: OpenRouter provider pinning refused", result.stderr)
        for sentinel in self.LAUNCH_ROUTE_SENTINELS:
            self.assertNotIn(sentinel, result.stderr)
        # It names the grammar the operator should have used instead of only what was wrong.
        self.assertIn("config set providers.<name>.modelOpenRouterRouting", result.stderr)

    def test_the_configure_help_surfaces_name_the_one_admitted_config_write(self) -> None:
        # Two help surfaces claim the plane is closed; a closed-list claim that omits the one
        # exception is false. Both are asserted, and each must also still say the rest is refused.
        for arguments in (("configure",), ("configure", "--help")):
            with self.subTest(arguments=arguments):
                result, log = self.run_launcher(*arguments)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("modelOpenRouterRouting", result.stdout)
                self.assertIn("mutation/import/export", result.stdout)
                self.assertOnlyReadOnlyOcxRoutes(log)

    def test_configure_allows_non_anthropic_provider_and_preserves_arguments(self) -> None:
        result, log = self.run_launcher("configure", "login", "xai", "two words")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertExactTracedOcxRoute(log, "login", "xai", "two words")

    # THE ALLOWLIST IS THE ADMISSION RULE for a provider that is not in the config file yet, and
    # nothing pinned its CONTENTS. A registry name opencodex serves but this list has never heard
    # of is refused, which is the correct default and also a silent papercut when the registry
    # grows: the five names opencodex 2.28.0 added over 2.11.1 were refused by a wrapper that was
    # otherwise fully current. Each is named here, so dropping one from
    # `known_non_anthropic_provider` fails this test instead of surfacing as an operator's
    # unexplained exit 3. MEASURED on a /tmp copy with `novita` removed from the case list: this
    # test fails on that subTest and the whole rest of the module still passes.
    def test_configure_admits_every_registry_provider_name_the_allowlist_claims(self) -> None:
        for provider in (
            "chutes", "featherless", "nous", "novita", "xiaomi-mimo",
            # 2.11.1-era names, kept so a rewrite of the list cannot narrow it silently.
            "xai", "openrouter", "groq", "xiaomi",
        ):
            with self.subTest(provider=provider):
                # An EMPTY config is the case under test: absent from the config file is what
                # sends classification to the allowlist rather than to a baseUrl.
                result, log = self.run_launcher("configure", "login", provider, config={"providers": {}})

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertExactTracedOcxRoute(log, "login", provider)

    def test_configure_still_refuses_a_provider_no_allowlist_entry_claims(self) -> None:
        # The positive control for the test above: absence from the config file must not admit by
        # itself. If this passes while the list is empty, that test proves nothing.
        result, log = self.run_launcher(
            "configure", "login", "not-a-registry-provider", config={"providers": {}}
        )

        self.assertEqual(result.returncode, 3)
        self.assertOnlyReadOnlyOcxRoutes(log, "<ocx><config><show><--json>")

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
        # The forwarded route, not merely a trace file: `ocx --version` creates that file before
        # any route runs, so its existence proved only that the preflight happened.
        #
        # THE COMPLETE route, INCLUDING `--api-key` and its value. Truncating the expectation
        # before the key flag -- to keep the sentinel out of assertion output -- meant a
        # `cmd_configure` that silently dropped `--api-key` and its value before forwarding still
        # PASSED, which is exactly the silent drop this test exists to catch. MEASURED on
        # 2026-08-11 against a scratch copy patched to drop the flag: the truncated form passed,
        # this form fails.
        self.assertFullRouteWithRedactedFailure(
            log,
            "provider", "add", "custom-vendor", "--base-url",
            "https://models.example.test/v1", "--api-key", secret,
        )

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
                result, log = self.run_launcher("configure", *arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                # Admitted AND forwarded. Exit 0 alone was satisfied by a wrapper that printed its
                # banner and ran nothing, which is the same observable as an inspection route that
                # silently stopped being reachable.
                self.assertIn(self.traced_ocx_route(*arguments), log.read_text())

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
                result, log = self.run_launcher("configure", *arguments, config=config)

                self.assertEqual(result.returncode, 0, result.stderr)
                # THE MUTATION FIRST. "Run `ocx sync`, then restart" is advice about a write that
                # landed; printed over a write that never ran it is a false instruction that sends
                # the operator to sync nothing and restart for no reason. This test asserted only
                # the advice, so it passed with the whole passthrough gutted -- while its sibling
                # test_failed_mutation_prints_no_sync_notice failed, making the pair asymmetric in
                # exactly the direction that hides a missing mutation.
                self.assertIn(self.traced_ocx_route(*arguments), log.read_text())
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
                result, log = self.run_launcher("configure", *arguments, config=config)
                self.assertEqual(result.returncode, 0, result.stderr)
                # The absence of the notice only means something if the route actually ran: a
                # gutted passthrough prints no notice either.
                self.assertIn(self.traced_ocx_route(*arguments), log.read_text())
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
        # A warning, never a refusal: upstream `provider add` has no stdin alternative, so the
        # route must still be FORWARDED. `log.exists()` could not tell that from a wrapper that
        # warned and then dropped the command, because `ocx --version` had already created the file.
        # Neither could a route expectation that stopped before `--api-key`: warning about a
        # credential in argv and then dropping that credential is the same observable, and it is
        # the failure mode this test is named for. So the KEY FLAG AND ITS VALUE are in the
        # expectation, with the failure message redacted (see assertFullRouteWithRedactedFailure).
        self.assertFullRouteWithRedactedFailure(
            log,
            "provider", "add", "custom-vendor", "--base-url",
            "https://models.example.test/v1", "--api-key", secret,
        )

    def test_no_argv_credential_warning_without_a_key_flag(self) -> None:
        arguments = (
            "provider", "add", "custom-vendor", "--base-url", "https://models.example.test/v1",
        )
        result, log = self.run_launcher("configure", *arguments)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("WARNING", result.stderr)
        # Same reason as its sibling above: silence about a route that never ran is not evidence.
        self.assertIn(self.traced_ocx_route(*arguments), log.read_text())

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

    def test_a_gateway_http_contact_is_traced_and_classified_as_contact(self) -> None:
        # THE GUARD ON THE GUARD. Three call sites reach the gateway over HTTP rather than through
        # `ocx` -- gateway_uptime_seconds, gateway_half_up, live_catalog_model_ids -- and while the
        # curl stub traced nothing, every "did not contact a gateway" assertion in this file was
        # blind to all three: a refusal reordered below a probe would have passed. This pins both
        # halves so that cannot go quiet again. `status` is the positive control, being the route
        # that legitimately DOES contact the gateway: the trace must show the contact, and
        # assertOnlyReadOnlyOcxRoutes must reject a trace that contains one.
        _, log = self.run_launcher(
            "status",
            provider_list_json={"configured": [{"name": "openai", "isDefault": True}]},
            catalog_json={"data": [{"id": "gpt-5.6-terra"}]},
        )

        trace = log.read_text()
        contacts = [line for line in trace.splitlines() if line.startswith("<curl>")]
        # Both HTTP call sites `status` reaches: the uptime nicety and the live-catalog read.
        self.assertIn("http://127.0.0.1:10100/healthz", "".join(contacts))
        self.assertIn("http://127.0.0.1:10100/v1/models", "".join(contacts))
        with self.assertRaises(AssertionError):
            self.assertOnlyReadOnlyOcxRoutes(log)

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

    # --- jq is an EXACT execution dependency at a trust boundary (ADR-0020) ----------------
    #
    # THE DEFECT (agentic-sdlc-6f9d, CodeRabbit on PR #4, fixed 2026-08-21). The resolver read
    # `${AGENTIC_SDLC_JQ:-$(type -P jq)}` and reached the pinned route only when PATH had no jq at
    # all, so a source-checkout launch classified settings documents, a provider config, and a
    # gateway catalog with whatever binary the caller's PATH named first. ADR-0020's compliance rule
    # is explicit -- "a readiness-dependent executable is never selected from ambient PATH without an
    # admitted exact identity" -- and this dependency decides REFUSALS next to credentials, so a
    # substituted jq that answers `clean` is a silent bypass of every settings check in the file.
    #
    # The first two tests below plant a hostile jq at the HEAD of PATH while the pinned route
    # resolves normally. Neither asserts a spelling of the resolver; both assert the two facts that
    # matter -- the hostile binary never ran, and the verdict came from the admitted route. The two
    # after them close the same substitution reached through the binding itself.

    # EVERY ONE OF THE FOUR TESTS BELOW ASSERTS THAT A HOSTILE STUB DID NOT RUN, and the fixture
    # only plants that stub when the host has a real jq to serve the pinned route with. Without the
    # skip, `assertFalse(marker.exists())` on a jq-less host passes against a stub that was never
    # written -- the vacuous-negative shape recorded in `host-dependent-tests-hide-clean-machine-
    # failures`. The skip states the dependency instead of silently reporting a pass.
    @unittest.skipUnless(shutil.which("jq"), "a real jq is required to plant a different one")
    def test_a_different_jq_on_path_is_never_used_for_the_settings_trust_boundary(self) -> None:
        result, log = self.run_launcher(
            "launch",
            global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}},
            hostile_path_jq=True,
        )

        # The verdict came from the admitted route: the hostile stub answers `clean` to every
        # program it is handed, so a launch that consulted it would have passed this document.
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("CLAUDE_CODE_USE_BEDROCK", result.stderr)
        self.assertFalse(
            self.hostile_jq_marker.exists(),
            "a jq at the head of PATH was executed for a trust-boundary parse: "
            + (self.hostile_jq_marker.read_text() if self.hostile_jq_marker.exists() else ""),
        )
        self.assertOnlyReadOnlyOcxRoutes(log)

    @unittest.skipUnless(shutil.which("jq"), "a real jq is required to plant a different one")
    def test_a_different_jq_on_path_is_never_used_for_the_live_catalog_comparison(self) -> None:
        # The same substitution reached through `status` rather than through a refusal: these are the
        # readers that parse the provider config and the RUNNING gateway's catalog.
        result, _ = self.run_launcher(
            "status",
            provider_list_json={"configured": [
                {"name": "openai", "isDefault": True},
                {"name": "muse", "isDefault": False},
            ]},
            catalog_json={"data": [{"id": "gpt-5.6-terra"}]},
            hostile_path_jq=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        # Real jq sees muse configured and absent from the catalog. The hostile stub's `clean`
        # collapses both lists to one identical name and reports every provider live.
        self.assertIn("NOT-LIVE", result.stdout)
        self.assertIn("muse", result.stdout)
        self.assertFalse(
            self.hostile_jq_marker.exists(),
            "a jq at the head of PATH was executed for a catalog parse: "
            + (self.hostile_jq_marker.read_text() if self.hostile_jq_marker.exists() else ""),
        )

    # REMOVING THE PATH ROUTE MAKES HAND-SETTING $AGENTIC_SDLC_JQ THE NATURAL OPERATOR REMEDY, so
    # the variable is now the highest-priority channel with nothing behind it. Both routes above are
    # exact by construction; the binding is exact only if it is CHECKED. An unvalidated binding
    # re-opens the whole defect one level up: a bare `gojq` resolves through ambient PATH, a bare
    # `jq` re-enters the shell function until bash core-dumps -- and that death lands inside
    # `offending="$(bypassing_settings_document_and_key)"`, where any nonzero exit reads as "every
    # document was read and held nothing". The suppression is therefore silent in both shapes.
    #
    # A lowercase `resolved_jq` in the environment is the same problem from the other side: it is
    # the resolver's own cache variable, so an inherited value is a third route that outranks both
    # admitted ones without ever being validated.
    #
    # Neither test spells the resolver. Both assert the two facts that matter -- the stub never ran,
    # and the refusal the hostile `clean` would have suppressed still fired.
    @unittest.skipUnless(shutil.which("jq"), "a real jq is required to plant a different one")
    def test_a_bare_name_binding_is_never_resolved_from_ambient_path(self) -> None:
        result, _ = self.run_launcher(
            "launch",
            global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}},
            hostile_path_jq=True,
            parent_env={"AGENTIC_SDLC_JQ": "jq-shim"},
        )

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertFalse(
            self.hostile_jq_marker.exists(),
            "a bare-name binding was resolved from PATH: "
            + (self.hostile_jq_marker.read_text() if self.hostile_jq_marker.exists() else ""),
        )

    @unittest.skipUnless(shutil.which("jq"), "a real jq is required to plant a different one")
    def test_an_inherited_resolved_jq_variable_is_not_an_admitted_route(self) -> None:
        result, _ = self.run_launcher(
            "launch",
            global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}},
            hostile_path_jq=True,
            parent_env={"resolved_jq": "jq-shim"},
        )

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertFalse(
            self.hostile_jq_marker.exists(),
            "an inherited resolved_jq preempted the admitted routes: "
            + (self.hostile_jq_marker.read_text() if self.hostile_jq_marker.exists() else ""),
        )

    # THE OTHER HALF OF THE FIX, and the reason a one-line resolution change was reverted once:
    # taking PATH away is only safe if every consumer that guards a refusal fails CLOSED when the
    # admitted route genuinely cannot run. AGENTS.md is unambiguous that an uncheckable explicit
    # `--settings` value stops the launch at exit 3, and a persistent document that carries a
    # routing switch must not become invisible because the tool that reads it is gone.
    #
    # Both of these bind a BROKEN exact jq while leaving a perfectly good one on PATH, so each run
    # proves two things at once: the surface refuses, and the ambient copy is not quietly borrowed
    # as a fallback (ADR-0020 decision 4 -- no silent substitution).

    def test_an_explicit_settings_value_is_refused_when_no_admitted_jq_route_runs(self) -> None:
        selected_name = "explicit-settings-OCX_PATH_SECRET.json"

        result, log = self.run_launcher(
            "launch", "--settings", selected_name,
            selected_settings_raw='{"env":{}}',
            selected_settings_name=selected_name,
            bound_jq_missing=True,
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("could not be checked", result.stderr)
        self.assertIn("jq", result.stderr)
        # The unverifiable path is still never echoed, on the same rule as every other refusal here.
        self.assertNotIn("OCX_PATH_SECRET", result.stdout + result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_persistent_settings_document_is_refused_when_no_admitted_jq_route_runs(self) -> None:
        # The document channel, which is the one an operator forgets: it is read on every launch,
        # and this one really does carry a routing switch. Reporting it as clean because jq could not
        # run would print a gateway banner over traffic that went to Bedrock instead.
        result, log = self.run_launcher(
            "launch",
            global_settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}},
            bound_jq_missing=True,
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("could not be checked", result.stderr)
        self.assertIn("settings.json", result.stderr)
        self.assertOnlyReadOnlyOcxRoutes(log)

    def test_a_configure_mutation_names_the_tool_when_no_admitted_jq_route_runs(self) -> None:
        # `refuse_missing_jq` had no test at all, and its text NAMES routes and fix commands -- the
        # class of sentence that rots without anything failing. Two things are pinned here: the
        # classification (a MISSING TOOL, never an unclassifiable provider, which is the misdirection
        # the status-4 split was introduced to end) and the two routes it points at.
        result, log = self.run_launcher(
            "configure", "account", "add-key", "muse",
            config={"providers": {"muse": {"baseUrl": "https://api.meta.ai/v1"}}},
            bound_jq_missing=True,
            stdin="",
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("MISSING TOOL", result.stderr)
        self.assertIn("AGENTIC_SDLC_JQ", result.stderr)
        # Both admitted routes, named in the order the refusal lists them: a caller-supplied
        # exact absolute override, then this checkout's pinned `mise exec -- jq`.
        self.assertIn("$AGENTIC_SDLC_JQ", result.stderr)
        self.assertIn("exec -- jq", result.stderr)
        # The real remedy: no lifecycle sets $AGENTIC_SDLC_JQ any more now that the
        # operator-tools PATH plane that used to bind it is gone, so the pinned `mise exec`
        # route is the one to fix with an explicit `--locked install`.
        self.assertIn("the operator-tools PATH plane", result.stderr)
        self.assertIn("that bound it is deleted", result.stderr)
        self.assertIn("--locked install", result.stderr)
        self.assertNotIn("anthropic-or-unclassifiable-provider", result.stderr)
        self.assertNotIn("approved opencodex configuration route", result.stdout)
        # Classification legitimately reads the provider config, and nothing else may have run.
        self.assertOnlyReadOnlyOcxRoutes(log, "<ocx><config><show><--json>")

    def test_status_reports_unknown_rather_than_a_false_not_live_when_a_read_fails(self) -> None:
        # The catalog comparison is a DISPLAY, so its honest degrade is `unknown` rather than a
        # refusal -- but `unknown` and a false alarm are not the same degrade. The default provider
        # serves BARE model ids, so it is never in the `<name>/` set the live catalog yields; if the
        # default-provider read is swallowed instead of propagated, the default provider itself is
        # reported NOT-LIVE, which is exactly the wrong verdict this section exists to avoid.
        result, _ = self.run_launcher(
            "status",
            provider_list_json={"configured": [
                {"name": "openai", "isDefault": True},
                {"name": "muse", "isDefault": False},
            ]},
            catalog_json={"data": [{"id": "muse/muse-spark-1.2"}, {"id": "gpt-5.6-terra"}]},
            bound_jq_refuses_default_provider_read=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unknown", result.stdout)
        self.assertNotIn("NOT-LIVE", result.stdout)

    def test_the_jq_resolver_does_not_recurse_into_itself(self) -> None:
        # The resolver is a shell function NAMED `jq`, so probing with `command -v jq` would find
        # the function and recurse until the shell died -- the same shadowing class that let a stale
        # `ccodex` shell function hide the installed binary. Since the ADR-0020 fix the resolver
        # probes no NAME at all (`$AGENTIC_SDLC_JQ`, else the pinned mise route), so the hazard is
        # closed by construction rather than by choosing `type -P` over `command -v`; this stays as
        # the guard that a future resolver does not reintroduce a name lookup.
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

    def test_launch_help_documents_yolo_as_an_explicit_unsafe_wrapper_option(self) -> None:
        for route in ("launch", "launch-ultracode"):
            with self.subTest(route=route):
                result, _ = self.run_launcher(route, "--help")

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("[--yolo]", result.stdout)
                self.assertIn("--dangerously-skip-permissions", result.stdout)
                self.assertIn("unsafe", result.stdout.lower())
                self.assertIn("-- --yolo", result.stdout)

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


@unittest.skipIf(
    BASH is None or os.name == "nt",
    "bash launcher fixtures require a POSIX bash; Git Bash's MSYS path/argv conversion"
    " rewrites argv and paths",
)
class BoundOcxInterpreterTests(unittest.TestCase):
    """agentic-sdlc-21f4: a bound `ocx` whose INTERPRETER is unreachable, and what it says.

    Deliberately not on the harness above, which drives the direct-checkout `mise exec` route and so
    can never reach this branch: `mise exec` puts the pinned node on PATH for free, and the defect
    exists only where an operator-tools install binds the ocx PATH and execs it itself. The fixture
    is the real shape from the container that found it — a `#!/usr/bin/env node` script that is
    present and executable, on a PATH with no node.
    """

    def plane(self, root: Path, *, body: str = '#!/usr/bin/env node\nconsole.log("2.28.0");\n') -> Path:
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (root / "home").mkdir(exist_ok=True)
        ocx = bin_dir / "ocx"
        ocx.write_text(body, encoding="utf-8")
        ocx.chmod(0o755)
        # A PATH with the handful of utilities the script itself needs and NO node, so "node is
        # unreachable" is a property of the fixture rather than of the machine running the suite.
        for utility in ("printf", "cat", "env", "sh", "bash", "dirname", "grep", "tr", "sed"):
            resolved = shutil.which(utility)
            if resolved:
                (bin_dir / utility).symlink_to(resolved)
        return ocx

    def ensure(self, root: Path, ocx: Path, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(BASH), str(SCRIPT), "ensure"],
            env={
                "HOME": str(root / "home"),
                "PATH": str(root / "bin"),
                "AGENTIC_SDLC_OCX": str(ocx),
                **extra,
            },
            text=True,
            capture_output=True,
            check=False,
        )

    def test_an_unreachable_interpreter_is_named_instead_of_blaming_the_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ocx = self.plane(root)

            result = self.ensure(root, ocx)

            self.assertEqual(result.returncode, 1)
            self.assertIn("its interpreter `node` is not reachable", result.stderr)
            self.assertIn(str(ocx), result.stderr)
            # The wrong remedy is the defect, so its absence is the assertion: `mise --locked
            # install` had already succeeded on the host that hit this.
            self.assertNotIn("pinned opencodex is not installed", result.stderr)
            # The real remedy: $AGENTIC_SDLC_OCX is orphaned now that the operator-tools PATH
            # plane that used to set it is gone, so the fix is to unset it and either put the
            # bare interpreter on PATH or bind one beside the executable.
            self.assertIn(
                "operator-tools PATH plane that bound it is deleted", result.stderr
            )
            self.assertIn(
                "put a `node` on PATH, or bind one beside the executable", result.stderr
            )

    def test_a_bound_interpreter_makes_the_same_fixture_start(self) -> None:
        # Positive control for the binding: nothing about the ocx script changed, only that the
        # install bound an interpreter, and the same invocation now gets past require_ocx.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ocx = self.plane(root)
            node_dir = root / "node" / "bin"
            node_dir.mkdir(parents=True)
            (node_dir / "node").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            (node_dir / "node").chmod(0o755)

            result = self.ensure(root, ocx, AGENTIC_SDLC_NODE=str(node_dir / "node"))

            self.assertNotIn("is not reachable", result.stderr)
            self.assertNotIn("pinned opencodex is not installed", result.stderr)

    def test_an_absolute_shebang_is_checked_as_a_file_not_as_a_name(self) -> None:
        # A `#!/abs/path/node` names one exact file, so PATH is irrelevant to whether it can start.
        # This fixture DOES have a working `node` on PATH: resolving the shebang by basename would
        # find it, call the interpreter reachable, and fall back to the wrong remedy again.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ocx = self.plane(root, body="#!/opt/absent-node/bin/node\nconsole.log('x');\n")
            real_node = shutil.which("node")
            if real_node:
                (root / "bin" / "node").symlink_to(real_node)
            else:
                (root / "bin" / "node").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                (root / "bin" / "node").chmod(0o755)

            result = self.ensure(root, ocx)

            self.assertEqual(result.returncode, 1)
            self.assertIn("its interpreter `/opt/absent-node/bin/node` is not reachable", result.stderr)
            self.assertIn("restore that exact interpreter", result.stderr)
            self.assertNotIn("pinned opencodex is not installed", result.stderr)

    def test_an_ocx_that_is_broken_for_any_other_reason_keeps_the_original_message(self) -> None:
        # The split must not become a blanket replacement: an executable that runs and fails has a
        # reachable interpreter, so it is still reported as the install problem it is.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ocx = self.plane(root, body="#!/bin/sh\nexit 3\n")

            result = self.ensure(root, ocx)

            self.assertEqual(result.returncode, 1)
            self.assertIn("pinned opencodex is not installed", result.stderr)
            self.assertNotIn("is not reachable", result.stderr)


if __name__ == "__main__":
    unittest.main()
