#!/usr/bin/env python3
"""Drive the committed ``bin/ccodex`` as a real subprocess: argv in, output and disk state out.

WHY THIS EXISTS.  Two published prereleases (v0.7.3, v0.7.4) shipped a ``ccodex sdlc`` plane that
refused itself at exit 3 from the only downloadable artifact, because the route was the shared
``uv run --script`` runner and ``runtime_admission()`` in ``scripts/ccodex_sdlc.py`` refuses every
execution shape that is not a direct isolated ``-I -B`` invocation.  ``cd3fd3d`` fixed the route and
added two tests; ``.github/workflows/release.yml`` now gates the shipped ARCHIVE.  This module is the
CHECKOUT half of the same net (gh #13's G1, wave W0 of the front-door program): it drives the
committed dispatcher over the whole ``sdlc`` grammar, so a language- or route-level refactor is a
provable change rather than a bet.

WHAT IS UNDER TEST, AND WHAT IS NOT.  The subject is ``<tree>/bin/ccodex`` executed as a process,
plus everything downstream of it inside the tree: the route it builds, the argv it forwards, the
report the reader emits on stdout, the refusal it emits on stderr, and the bytes left on disk.  It is
NOT a substitute for the in-process unit suites, which own the reader's grammar, the report schema,
and each lifecycle module's own refusal ladder; a seam case asserts that an invocation reaches its
decision intact, not that the decision is exhaustively correct.

THE METHODOLOGICAL RULE, INHERITED FROM `scripts/smoke_release.py`.  Every case asserts OUTPUT
CONTENT.  Exit 3 is a legitimate status on this surface -- a refusal before any effect -- so an exit
code alone cannot separate "this host has no activation to uninstall" from "the dispatcher built the
wrong interpreter invocation".  ``SeamCase.assertions_declared`` therefore refuses a case that
carries no content assertion, and every lifecycle case forbids the admission text on stderr, which is
what makes it a direct negative for the v0.7.4 regression rather than a case a broken dispatcher
could satisfy by refusing for the wrong reason.

NO TRUST IS GRANTED AND NO TOOL IS RESOLVED.  ``bin/ccodex`` refuses an untrusted root before any
route, and granting real trust in a test would be a persistent operator mutation; resolving the real
pinned toolchain would download an interpreter.  A recording stub ``mise`` stands at that boundary
instead.  It is faithful in the ONE property the mutation lever depends on: it serves BOTH routes the
dispatcher can build -- ``uv python find`` answers with this suite's own interpreter, which the
dispatcher then execs directly under ``-I -B``, and ``uv run --python 3.12.11 --script`` execs that
same interpreter with NO isolation flags, exactly as real ``uv run`` does.  So a route regression
reaches the REAL reader through a genuinely non-isolated interpreter and is refused by the reader's
own admission, by name, instead of dying on a stub that declined to play along.  What the stub does
NOT prove is mise's own wording: that the string mise prints for an untrusted config really contains
``not trusted`` is measured against REAL mise in ``tests/test_bin_ccodex.py``, on a real extracted
archive, and this module deliberately does not restate it.

HOST-STATE INDEPENDENCE.  Every case runs with an allowlist environment whose ``HOME``,
``XDG_STATE_HOME``, and ``XDG_DATA_HOME`` are fresh scratch directories, so the reader's projections
describe the fixture rather than the developer's machine.  The one deliberately host-shaped
assertion, ``bundle status``'s terminal line, is matched by the pattern that accepts BOTH shapes the
product can emit.

WINDOWS.  ``bin/ccodex`` is a bash script and Windows resolves an interpreter from the PE header
rather than a shebang, so ``CreateProcess`` on it raises ``[WinError 193] %1 is not a valid Win32
application``; the fixtures also build a POSIX-shell stub on an ``os.symlink`` allowlist PATH.  The
executing suites skip on ``nt`` by name, and on any filesystem that cannot carry an executable bit.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(os.path.realpath(Path(__file__).resolve().parents[1]))
BIN_CCODEX = ROOT / "bin" / "ccodex"
MUTATION_PATCH = ROOT / ".github" / "mutations" / "restore-v0.7.4-uv-run-sdlc-route.patch"

#: Expanded in every declared assertion, so one case text serves the intact tree and the regressed
#: fixture without either hard-coding a path (the smoke manifest's ``{tree}`` token, same purpose).
ROOT_TOKEN = "{root}"

#: The base utilities the dispatcher itself may reach for. A positive isolation, not a stripped
#: PATH: ``bash`` has to be findable because ``#!/usr/bin/env bash`` resolves it by name.
DISPATCHER_UTILITIES = ("bash", "cat", "dirname", "realpath")

#: The two strings the release workflow's mutation job requires (``--require-marker``). The first is
#: the report's own ``findings[].code``; the second is ``runtime_admission()``'s refusal detail, and
#: it is the only one a lifecycle verb's stderr carries, because a lifecycle refusal renders no
#: report.
ROUTE_REGRESSION_MARKERS = ("runtime-admission-refused", "expected direct -I -B execution")

DISPATCHER_IS_POSIX_SHELL_SKIP_REASON = (
    "bin/ccodex is a POSIX shell dispatcher that Windows cannot execute directly (WinError 193),"
    " and this harness builds its stub toolchain on a symlinked POSIX allowlist PATH"
)
PINNED_INTERPRETER_SKIP_REASON = (
    "the seam hands this suite's own interpreter to the REAL reader, whose runtime admission demands"
    " exactly 3.12.11 (the repository gate runs the suite under it)"
)


def _load_installer():
    """Load `install_skill_bundle` for FIXTURE CONSTRUCTION only, once, by absolute path.

    The subject under test is still the dispatcher as a subprocess; this import exists so a planted
    ownership document is the installer's own shape rather than a second hand-typed spelling of it.
    Nothing here calls a lifecycle mutator, and `Config(dry_run=True)` is passed so a helper that
    ever grew a write would refuse rather than touch the fixture.
    """
    global _INSTALLER
    if _INSTALLER is None:
        spec = importlib.util.spec_from_file_location(
            "_seam_harness_installer", ROOT / "scripts" / "install_skill_bundle.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _INSTALLER = module
    return _INSTALLER


_INSTALLER: Any = None


def executable_bit_is_honored() -> bool:
    """Probe, never assume: some mounts drop the executable bit and no chmod restores it."""
    try:
        with tempfile.TemporaryDirectory(prefix="seam-exec-probe-") as temporary:
            probe = Path(temporary) / "probe.sh"
            probe.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
            probe.chmod(probe.stat().st_mode | stat.S_IXUSR)
            return os.access(probe, os.X_OK)
    except OSError:
        return False


EXECUTABLE_BIT_IS_HONORED = executable_bit_is_honored()
EXECUTABLE_BIT_SKIP_REASON = (
    "this filesystem does not honor an executable bit, so neither the stub toolchain nor a copied"
    " dispatcher can be executed here"
)


# ---- the case inventory --------------------------------------------------------------------------


@dataclass(frozen=True)
class SeamCase:
    """One argv driven through one tree, and every observation declared about its output.

    ``route_sensitive`` is the mutation lever's own bookkeeping: True means this case's declared
    assertions cannot all hold once the ``sdlc`` route regresses to ``uv run --script``.  False
    requires ``insensitivity_reason``, because a case that survives the regression is either a
    deliberate control or a case that has stopped proving anything, and the difference has to be
    written down rather than inferred.
    """

    identifier: str
    argv: tuple[str, ...]
    expect_exit: int
    route_sensitive: bool
    insensitivity_reason: str = ""
    state: str = "clean"
    mise: str = "trusted"
    stdout_present: tuple[str, ...] = ()
    stdout_absent: tuple[str, ...] = ()
    stdout_matches: tuple[str, ...] = ()
    stdout_empty: bool = False
    stderr_present: tuple[str, ...] = ()
    stderr_present_any: tuple[str, ...] = ()
    stderr_absent: tuple[str, ...] = ()
    stderr_matches: tuple[str, ...] = ()
    json_paths: dict[str, Any] = field(default_factory=dict)
    require_finding_codes: tuple[str, ...] = ()
    forbid_finding_codes: tuple[str, ...] = ()
    canonical_json_stdout: bool = False

    @property
    def assertions_declared(self) -> int:
        """How many CONTENT assertions this case carries; zero is refused by the meta-test."""
        return sum(
            (
                len(self.stdout_present),
                len(self.stdout_absent),
                len(self.stdout_matches),
                len(self.stderr_present),
                1 if self.stderr_present_any else 0,
                len(self.stderr_absent),
                len(self.stderr_matches),
                len(self.json_paths),
                len(self.require_finding_codes),
                len(self.forbid_finding_codes),
                1 if self.stdout_empty else 0,
                1 if self.canonical_json_stdout else 0,
            )
        )


#: Every reader verb renders one semantic report, so the admitted assertions are shared rather than
#: retyped per verb: a drift in one verb's runtime block is a drift in all four.
_ADMITTED_RUNTIME = {
    "runtime.state": "admitted",
    "runtime.isolated": True,
    "runtime.version": "3.12.11",
    "overall.exit_class": "ok",
}
_ADMITTED_HUMAN_LINE = "runtime: admitted (3.12.11, isolated=true)"
_HUMAN_NEVER = ("runtime: refused", "Traceback", "runtime-admission-refused")

#: A well-formed digest that approves nothing, so ``recover --apply`` reaches its module's own
#: "nothing to recover" refusal instead of the parser's malformed-digest usage error.
_UNAPPROVED_DIGEST = "0" * 64

#: The reason each lifecycle verb refuses on a host with no activation, as a per-platform
#: alternation. Linux and Darwin refuse for DIFFERENT reasons -- an absent candidate or receipt
#: versus the uncertified-platform gate -- and each fragment below is a literal in its own module's
#: source, which ``SeamInventoryTest`` re-checks so a reworded refusal fails the gate loudly instead
#: of silently weakening this assertion to nothing.
LIFECYCLE_OWN_REASON = {
    "install": ("no acquired candidate is available", "certified only on"),
    "update": ("no usable active distribution-activation receipt", "certified only on"),
    # On a host with neither a pointer NOR an ownership document, the uninstall ladder runs out of
    # rungs and names both: the receipt it looked for and the ownership rows it looked for. A host with
    # rows but no receipt is a different state (the announced legacy-unreceipted retirement), so this
    # fragment is the empty-host one deliberately.
    "uninstall": ("no installer ownership document", "only and refuses on"),
    "recover-apply": ("found nothing to recover on this host", "resumes an activated"),
}
LIFECYCLE_REASON_SOURCES = {
    "install": "ccodex_sdlc_install.py",
    "update": "ccodex_sdlc_update.py",
    "uninstall": "ccodex_sdlc_uninstall.py",
    "recover-apply": "ccodex_sdlc_recover.py",
}


def _reader_json_case(
    verb: str,
    argv: tuple[str, ...],
    extra_json: dict[str, Any] | None = None,
    stderr_present: tuple[str, ...] = (),
) -> SeamCase:
    return SeamCase(
        identifier=f"sdlc-{verb}-json-is-admitted-through-the-direct-isolated-route",
        argv=argv,
        expect_exit=0,
        route_sensitive=True,
        json_paths={
            "command.verb": "recover" if verb.startswith("recover") else verb,
            "checkout.plane": "checkout-development",
            "schema_version": "ccodex-sdlc-read-report/v1",
            **_ADMITTED_RUNTIME,
            **(extra_json or {}),
        },
        forbid_finding_codes=("runtime-admission-refused",),
        canonical_json_stdout=True,
        stderr_present=stderr_present,
    )


def _reader_human_case(
    verb: str,
    argv: tuple[str, ...],
    extra_stdout: tuple[str, ...] = (),
    stderr_present: tuple[str, ...] = (),
) -> SeamCase:
    rendered = "recover" if verb.startswith("recover") else verb
    return SeamCase(
        identifier=f"sdlc-{verb}-human-render-names-the-admitted-runtime",
        argv=argv,
        expect_exit=0,
        route_sensitive=True,
        stdout_present=(f"ccodex sdlc {rendered}:", _ADMITTED_HUMAN_LINE, "checkout: ") + extra_stdout,
        stdout_absent=_HUMAN_NEVER,
        stderr_present=stderr_present,
    )


def _lifecycle_case(identifier: str, argv: tuple[str, ...], verb: str, named: str) -> SeamCase:
    """A mutating verb reaching its own module's pre-effect refusal, never a mutation.

    The declared content is platform-independent on purpose: WHICH reason a lifecycle verb states is
    a platform fact (``policy/release-smoke.v1.json`` declares those per platform, on the shipped
    artifact), while what this seam owns is that the verb reached its own module, named ITSELF,
    refused before any effect, and did not touch the fixture.  The forbidden admission text is what
    makes the case fail the moment the route regresses.
    """
    return SeamCase(
        identifier=identifier,
        argv=argv,
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        stderr_present=(f"error: ccodex sdlc {named}",),
        stderr_present_any=LIFECYCLE_OWN_REASON[verb],
        stderr_absent=("expected direct -I -B execution", "Traceback", "is unavailable in this distribution"),
    )


def _plane_cases() -> tuple[SeamCase, ...]:
    """The three mutating verbs on BOTH receipted planes, refusing in their own name.

    Two agents, six cases, and that is the point of the wave that added the second one: a suite that
    only ever spelled ``claude`` would stay green with the codex arm re-pinned shut, so each admitted
    plane drives every verb here. What each case proves is narrow and route-sensitive -- the vector
    reached its own module through the isolated route, that module named ITSELF and its own reason, and
    the fixture is untouched -- which is exactly what a plane that refused as a GRAMMAR error (exit 2,
    ``unsupported ... host``) or fell through to another plane's module would fail.
    """
    cases: list[SeamCase] = []
    for verb in ("install", "update", "uninstall"):
        for agent in ("claude", "codex"):
            cases.append(
                _lifecycle_case(
                    f"sdlc-{verb}-on-the-{agent}-plane-reaches-its-module-and-refuses-before-any-effect",
                    ("sdlc", verb, "--host", agent),
                    verb,
                    verb,
                )
            )
    return tuple(cases)


SEAM_CASES: tuple[SeamCase, ...] = (
    # ---- the four reader verbs, canonical JSON -------------------------------------------------
    _reader_json_case("inspect", ("sdlc", "inspect", "--json")),
    _reader_json_case("status", ("sdlc", "status", "--json")),
    _reader_json_case("doctor", ("sdlc", "doctor", "--json")),
    _reader_json_case(
        "recover-dry-run",
        ("sdlc", "recover", "--dry-run", "--json"),
        extra_json={"command.dry_run": True, "recovery.effect": "none"},
        stderr_present=("recovery plan",),
    ),
    # ---- the same four verbs, human render -----------------------------------------------------
    _reader_human_case("inspect", ("sdlc", "inspect")),
    _reader_human_case("status", ("sdlc", "status")),
    _reader_human_case("doctor", ("sdlc", "doctor")),
    _reader_human_case(
        "recover-dry-run",
        ("sdlc", "recover", "--dry-run"),
        extra_stdout=("recovery: ",),
        stderr_present=("recovery plan",),
    ),
    # ---- planted state bytes reaching the report and the approval token -------------------------
    SeamCase(
        identifier="sdlc-doctor-reports-planted-lifecycle-state-bytes-it-was-given",
        argv=("sdlc", "doctor", "--json"),
        expect_exit=0,
        route_sensitive=True,
        state="bundle-pending",
        json_paths={
            "command.verb": "doctor",
            "overall.state": "blocked",
            "bundle.state": "blocked",
            **_ADMITTED_RUNTIME,
        },
        require_finding_codes=("pending-recovery",),
        forbid_finding_codes=("runtime-admission-refused",),
        stdout_present=("agentic-sdlc-installer",),
        # The deleted plane's report field must not come back under any name: an exact-key set
        # refuses it in-process, and this is the same claim read off the shipped dispatcher's stdout.
        stdout_absent=('"operator_tools"',),
        canonical_json_stdout=True,
    ),
    # The collapsed deprecation phase's one operator-facing promise, driven through the real
    # dispatcher: a store the deleted installer left behind is NAMED with its manual remedy, and it
    # does not block -- an upgraded host is not a degraded host.
    SeamCase(
        identifier="sdlc-doctor-names-the-retired-operator-tools-store-and-its-manual-remedy",
        argv=("sdlc", "doctor", "--json"),
        expect_exit=0,
        route_sensitive=True,
        state="retired-operator-tools-store",
        json_paths={
            "command.verb": "doctor",
            "overall.state": "absent",
            "bundle.state": "absent",
            **_ADMITTED_RUNTIME,
        },
        require_finding_codes=("foreign-state",),
        forbid_finding_codes=("runtime-admission-refused", "pending-recovery"),
        stdout_present=(
            "agentic-sdlc-operator-tools",
            "nothing in this distribution reads, resumes, or removes it",
            "by hand",
        ),
        stdout_absent=('"operator_tools"',),
        canonical_json_stdout=True,
    ),
    SeamCase(
        identifier="sdlc-recover-dry-run-offers-one-self-consistent-plan-digest-for-planted-state",
        argv=("sdlc", "recover", "--dry-run", "--json"),
        expect_exit=0,
        route_sensitive=True,
        state="bundle-pending",
        json_paths={
            "command.dry_run": True,
            "recovery.state": "proposed",
            "recovery.effect": "none",
            **_ADMITTED_RUNTIME,
        },
        # The approval token is stderr-only by design, and the SAME digest must appear in both
        # halves of the sentence: a backreference, so a line that offered one digest and told the
        # operator to approve another would fail rather than match a shape.
        stderr_matches=(
            r"recovery plan sha256 ([0-9a-f]{64}): approve exactly this plan with"
            r" `ccodex sdlc recover --apply \1`",
        ),
        forbid_finding_codes=("runtime-admission-refused",),
        canonical_json_stdout=True,
    ),
    # ---- the three mutating verbs on both planes, refusing before any effect --------------------
    *_plane_cases(),
    _lifecycle_case(
        "sdlc-recover-apply-reaches-its-module-and-refuses-before-any-effect",
        ("sdlc", "recover", "--apply", _UNAPPROVED_DIGEST),
        "recover-apply",
        "recover --apply",
    ),
    # ---- grammar arms that are decided BEFORE the runtime is admitted --------------------------
    # These are the mutation lever's controls. The reader parses argv before it admits an
    # interpreter, so a usage error is the same document on either route; a suite where EVERY case
    # went red under the patch would not distinguish "the route regressed" from "the fixture broke".
    SeamCase(
        identifier="an-unknown-sdlc-verb-is-a-usage-error-not-a-refusal",
        argv=("sdlc", "frobnicate"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "the reader parses argv before it admits a runtime, so an unknown verb is decided on"
            " either route; this case is the lever's control that the regression is scoped"
        ),
        stdout_empty=True,
        stderr_present=("error: unknown ccodex sdlc verb: 'frobnicate'", "usage: ccodex sdlc inspect"),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        identifier="a-bare-sdlc-route-names-the-whole-closed-grammar",
        argv=("sdlc",),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason="decided by the reader's parser before any runtime admission",
        stdout_empty=True,
        stderr_present=(
            "error: ccodex sdlc needs inspect, status, doctor, recover --dry-run, or one of install,"
            " update, uninstall with --host claude|codex",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        identifier="sdlc-install-without-a-host-is-a-usage-error-naming-the-missing-selector",
        argv=("sdlc", "install"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason="decided by the reader's parser before any runtime admission",
        stdout_empty=True,
        stderr_present=(
            "error: ccodex sdlc install requires an explicit --host claude|codex; there is no default"
            " host",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        # The selector is required on EVERY mutating verb, not only install: with two planes live a
        # bare `uninstall` would have to pick one, and whichever it picked would remove that agent's
        # bytes on the strength of an argument nobody typed.
        identifier="sdlc-uninstall-without-a-host-is-a-usage-error-and-never-a-default-plane",
        argv=("sdlc", "uninstall"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "the reader parses argv before it admits a runtime, so a missing selector is decided on"
            " either route; it is a control, and its subject is the grammar rather than the route"
        ),
        stdout_empty=True,
        stderr_present=(
            "error: ccodex sdlc uninstall requires an explicit --host claude|codex; there is no"
            " default host",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback", "no installer ownership document"),
    ),
    SeamCase(
        identifier="an-unadmitted-sdlc-host-is-a-usage-error-naming-the-admitted-planes",
        argv=("sdlc", "install", "--host", "gemini"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "an unadmitted selector is refused by the reader's parser before any runtime admission, so"
            " it is decided identically on either route; it is the positive control for the six"
            " admitted-plane cases above"
        ),
        stdout_empty=True,
        stderr_present=(
            "error: unsupported ccodex sdlc install host: 'gemini'; the admitted hosts are"
            " claude, codex",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        identifier="sdlc-help-is-answered-on-stdout-and-is-never-an-error",
        argv=("sdlc", "--help"),
        expect_exit=0,
        route_sensitive=False,
        insensitivity_reason="help is answered by the reader's parser before any runtime admission",
        stdout_present=(
            "usage: ccodex sdlc inspect [--json]",
            "ccodex sdlc install --host claude|codex",
            "ccodex sdlc update --host claude|codex",
            "ccodex sdlc uninstall --host claude|codex",
        ),
        stdout_absent=("Traceback",),
    ),
    # ---- boundaries the dispatcher owns, upstream of any interpreter ---------------------------
    SeamCase(
        identifier="an-untrusted-root-refuses-the-sdlc-route-naming-this-trees-own-remedy",
        argv=("sdlc", "status", "--json"),
        expect_exit=3,
        route_sensitive=False,
        insensitivity_reason=(
            "require_toolchain runs before either route is built, so the trust boundary refuses"
            " identically on both; it is a control, and REAL mise's wording is proven in"
            " tests/test_bin_ccodex.py"
        ),
        mise="untrusted",
        stdout_empty=True,
        stderr_present=(
            f"refused: {ROOT_TOKEN}/mise.toml is not trusted",
            f"mise trust {ROOT_TOKEN}/mise.toml",
        ),
        stderr_absent=("mise is not on PATH", "expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        identifier="a-probe-failure-that-is-not-a-trust-refusal-is-reported-as-unreadable",
        argv=("sdlc", "status", "--json"),
        expect_exit=1,
        route_sensitive=False,
        insensitivity_reason=(
            "the toolchain probe is upstream of both routes; this is the trust case's discriminator,"
            " proving the refusal above is classified from the probe's own text"
        ),
        mise="unreadable",
        stdout_empty=True,
        stderr_present=(f"error: mise cannot read {ROOT_TOKEN}:", "the fixture probe declined"),
        stderr_absent=("not trusted", "mise trust", "expected direct -I -B execution"),
    ),
    SeamCase(
        identifier="bundle-status-still-reaches-the-shared-uv-runner-and-ends-with-its-terminal-line",
        # The selector is REQUIRED as of the ledger-hygiene wave: `status` with no `--agent` now
        # refuses at exit 2 naming both planes, so a selector-free case here would assert a
        # deleted default instead of the route this case exists to observe.
        argv=("bundle", "status", "--agent", "claude"),
        expect_exit=0,
        route_sensitive=False,
        insensitivity_reason=(
            "the bundle route is ALREADY the shared uv runner, so the patch cannot change it; it is"
            " the lever's positive control that the stub's uv-run emulation works and that the"
            " regression is confined to the sdlc route"
        ),
        # Both terminal lines the product can emit. The fixture's state is empty, so the first is
        # what runs here; the alternation is what keeps the case honest on a populated host.
        stdout_matches=(
            r"(?m)^(?:no owned entries for this host \(run: mise run bundle:install\)"
            r"|[0-9]+ ok, [0-9]+ conflict, [0-9]+ absent)\s*\Z",
        ),
        stdout_absent=("Traceback", "error:"),
        stderr_absent=("Traceback",),
    ),
)


# ---- fixtures ------------------------------------------------------------------------------------


#: What the stub answers when the dispatcher probes the config. ``unreadable`` carries a text that
#: deliberately does NOT contain ``not trusted``, so the dispatcher must take its other branch.
_PROBE_BODIES = {
    "trusted": "    exit 0",
    "untrusted": (
        "    printf 'Config file %s/mise.toml is not trusted. Trust it with `mise trust`.\\n'"
        " \"$root\" >&2\n    exit 1"
    ),
    "unreadable": "    printf 'the fixture probe declined to parse this config\\n' >&2\n    exit 1",
}


def write_stub_mise(directory: Path, *, root: Path, interpreter: Path, log: Path, probe: str) -> Path:
    """A recording ``mise`` that serves BOTH routes the dispatcher can build, and nothing else.

    Faithfulness is the whole point.  ``uv python find`` answers with an interpreter the dispatcher
    then execs under ``-I -B``, which the reader admits; ``uv run --python 3.12.11 --script`` execs
    the SAME interpreter with no isolation flags, which is what real ``uv run`` does and what the
    reader refuses by name.  Any other argv exits 97 with the vector on stderr, so a route this
    harness has not reviewed is loud rather than silently absorbed.
    """
    stub = directory / "mise"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        f"root='{root.as_posix()}'\n"
        f"log='{log.as_posix()}'\n"
        f"interpreter='{interpreter.as_posix()}'\n"
        'printf \'%s\\n\' "$*" >> "$log"\n'
        'if [ "${1:-}" != "-C" ] || [ "${2:-}" != "$root" ]; then\n'
        "  printf 'unexpected mise argv: %s\\n' \"$*\" >&2\n"
        "  exit 97\n"
        "fi\n"
        "shift 2\n"
        'case "${1:-}" in\n'
        f"  tasks)\n{_PROBE_BODIES[probe]}\n    ;;\n"
        "  exec) shift ;;\n"
        "  *) printf 'unexpected mise argv: %s\\n' \"$*\" >&2; exit 97 ;;\n"
        "esac\n"
        'if [ "${1:-}" != "--" ]; then\n'
        "  printf 'unexpected mise exec argv: %s\\n' \"$*\" >&2\n"
        "  exit 97\n"
        "fi\n"
        "shift\n"
        'if [ "$*" = "uv python find --managed-python 3.12.11" ]; then\n'
        '  printf \'%s\\n\' "$interpreter"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "${1:-}" = "uv" ] && [ "${2:-}" = "run" ] && [ "${3:-}" = "--python" ] \\\n'
        '   && [ "${4:-}" = "3.12.11" ] && [ "${5:-}" = "--script" ]; then\n'
        "  shift 5\n"
        '  exec "$interpreter" "$@"\n'
        "fi\n"
        "printf 'unexpected mise exec argv: %s\\n' \"$*\" >&2\n"
        "exit 97\n",
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(0o755)
    return stub


def dispatcher_utilities_path(directory: Path) -> Path:
    """An allowlist PATH holding only the utilities ``bin/ccodex`` itself may reach for."""
    directory.mkdir(parents=True, exist_ok=True)
    for tool in DISPATCHER_UTILITIES:
        resolved = shutil.which(tool)
        if resolved and not (directory / tool).exists():
            os.symlink(resolved, directory / tool)
    return directory


#: The interrupted bundle transition the ``bundle-pending`` fixture plants: the installer's own
#: ownership shape with one armed ``pending`` slot, real state bytes written by the test rather than
#: by a lifecycle mutation, so the seam can prove a document on disk reaches the report and the
#: derived plan digest.
#:
#: IT REPLACED AN OPERATOR-TOOLS FIXTURE (gh #10 phase 4). The two cases below used to arm the PATH
#: plane's own store, which is deleted -- the reader projects no such plane, `derive_plan` reads no
#: such journal, and a case still arming it would have gone quietly green on a report that no longer
#: mentioned it. The bundle journal is the ONE surviving substrate that can carry an armed slot, so
#: the case's claim (planted state bytes reach the report and the approval token) is unchanged while
#: the subject moved. Built through the installer's own helpers rather than hand-typed JSON: the
#: document has to satisfy `validate_state` and `pending_selects_config`, and a hand-typed copy would
#: pass this fixture's own eye while failing the reader's, or drift silently when the schema moves.
def write_bundle_pending(state_root: Path, home: Path) -> Path:
    bundle = _load_installer()
    config = bundle.Config(ROOT, home, home / ".codex", "auto", True, "all", state_root)
    source = state_root / "seam-bundle-source" / "seam-pending-fixture"
    source.mkdir(parents=True, exist_ok=True)
    (source / "SKILL.md").write_text("---\nname: seam-pending-fixture\n---\n", encoding="utf-8")
    entry = bundle.Entry("claude", "skill", "seam-pending-fixture", source)
    destination = bundle.destination_for(entry, config)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copytree(source, destination)
    record = bundle.entry_record(entry, "copy", installed_digest=bundle.digest(destination))
    document = config.state_path
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(
        json.dumps(
            {
                "version": bundle.STATE_VERSION,
                "entries": {},
                "pending": bundle.pending_slot("install", str(destination), None, record),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


#: The leftover store the ``retired-operator-tools-store`` fixture plants. gh #10 phase 4 deleted the
#: PATH plane's module, its five mise tasks, and the `operator-tools:uninstall` verb, so an operator
#: who ran that installer still owns real bytes with nothing left to retire them. The reader names the
#: store and the manual remedy instead, and this fixture is how that promise is checked through the
#: real dispatcher rather than asserted in prose. The document's CONTENT is deliberately irrelevant --
#: an armed slot inside it is preserved and named, never resumed -- so what is planted is the
#: directory plus one file, which is exactly what an upgraded host has.
def write_retired_operator_tools_store(state_root: Path) -> Path:
    directory = state_root / "agentic-sdlc-operator-tools"
    directory.mkdir(parents=True, exist_ok=True)
    document = directory / "state.json"
    document.write_text(
        json.dumps({"version": 2, "entries": {}, "pending": None}, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


@dataclass(frozen=True)
class Observation:
    case: SeamCase
    root: Path
    returncode: int
    stdout: str
    stderr: str
    mise_argv: tuple[str, ...]
    #: The fixture's own before/after difference, digest by digest. ``created`` is a file that was
    #: not there, ``rewritten`` is one whose bytes moved, ``removed`` is one that left -- the three
    #: facts that separate a reader from a writer without trusting the verb's own account of itself.
    created: tuple[str, ...]
    rewritten: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def evidence(self) -> str:
        return f"{self.stdout}\n{self.stderr}"

    @property
    def effect(self) -> tuple[str, ...]:
        return self.created + self.rewritten + self.removed

    @property
    def transcript(self) -> str:
        lines = [
            f"argv: ccodex {' '.join(self.case.argv)}",
            f"exit: {self.returncode}",
            f"mise argv: {list(self.mise_argv)}",
            f"fixture effect: created={list(self.created)} rewritten={list(self.rewritten)}"
            f" removed={list(self.removed)}",
        ]
        for name, stream in (("stdout", self.stdout), ("stderr", self.stderr)):
            if stream.strip():
                lines.append(f"--- {name} ---")
                lines.extend(stream.splitlines())
        return "\n".join(lines)


class SeamRunner:
    """Run one case against one tree in its own scratch environment.

    ``scratch`` must outlive every observation the caller inspects; a ``unittest`` fixture owns it.
    """

    def __init__(self, scratch: Path, root: Path | None = None, interpreter: Path | None = None):
        self.scratch = Path(os.path.realpath(scratch))
        self.root = Path(os.path.realpath(root or ROOT))
        self.interpreter = Path(os.path.realpath(interpreter or Path(sys.executable)))
        self.utilities = dispatcher_utilities_path(self.scratch / "utilities")
        self._served = 0

    def run(self, case: SeamCase) -> Observation:
        self._served += 1
        cell = self.scratch / f"case-{self._served:03d}"
        home = cell / "home"
        state = cell / "state"
        data = cell / "data"
        working = cell / "cwd"
        stub_bin = cell / "stub-bin"
        for directory in (home, state, data, working, stub_bin):
            directory.mkdir(parents=True)
        if case.state == "bundle-pending":
            write_bundle_pending(state, home)
        elif case.state == "retired-operator-tools-store":
            write_retired_operator_tools_store(state)
        elif case.state != "clean":
            raise ValueError(f"{case.identifier} declares an unknown fixture state {case.state!r}")
        log = cell / "mise-argv.log"
        write_stub_mise(
            stub_bin,
            root=self.root,
            interpreter=self.interpreter,
            log=log,
            probe=case.mise,
        )
        before = self.inventory(cell)
        # An allowlist, not os.environ minus a blocklist: an inherited tool root or state root would
        # re-enter the route and make the report describe the developer's host.
        environment = {
            "PATH": os.pathsep.join([str(stub_bin), str(self.utilities)]),
            "HOME": str(home),
            "XDG_STATE_HOME": str(state),
            "XDG_DATA_HOME": str(data),
            "LANG": "C",
            "LC_ALL": "C",
            # The regressed route runs the reader WITHOUT ``-B``, exactly as ``uv run`` does, so it
            # writes bytecode; sending that cache into the fixture keeps the tree under test clean.
            # It changes no interpreter flag, so the admission refusal is still the route's own.
            "PYTHONPYCACHEPREFIX": str(cell / "pycache"),
        }
        completed = subprocess.run(
            [str(self.root / "bin" / "ccodex"), *case.argv],
            env=environment,
            cwd=str(working),
            capture_output=True,
            text=True,
            check=False,
        )
        after = self.inventory(cell)
        return Observation(
            case=case,
            root=self.root,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            mise_argv=tuple(log.read_text(encoding="utf-8").splitlines()) if log.exists() else (),
            created=tuple(sorted(set(after) - set(before))),
            rewritten=tuple(
                sorted(name for name, digest in after.items() if before.get(name, digest) != digest)
            ),
            removed=tuple(sorted(set(before) - set(after))),
        )

    #: Fixture bookkeeping the harness itself writes: the stub toolchain, its argv log, and the
    #: bytecode cache the regressed route legitimately produces. Everything else appearing under a
    #: cell is the invocation's own effect.
    HARNESS_OWNED = ("stub-bin", "mise-argv.log", "pycache")

    @classmethod
    def inventory(cls, cell: Path) -> dict[str, str]:
        """Every file under the fixture and its digest, so an effect is observed rather than trusted."""
        observed: dict[str, str] = {}
        for path in sorted(cell.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(cell)
            if set(relative.parts) & set(cls.HARNESS_OWNED):
                continue
            observed[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return observed


def build_regressed_tree(destination: Path, patch: Path = MUTATION_PATCH) -> Path:
    """A tree whose ``bin/ccodex`` is the v0.7.4 route, over THIS checkout's own scripts and policy.

    The dispatcher self-locates its root as the parent of its own ``bin/``, so restoring the route
    means standing up a root.  ``scripts`` and ``policy`` are symlinked directories rather than
    copies, so the regressed fixture executes the reader and policy bytes under test rather than a
    snapshot of them that could drift; the reader's own symlink refusals inspect the FINAL component
    of each path it loads, which a symlinked parent leaves a regular file.

    The mutation is applied by ``git apply`` from the tracked patch file, never by a string edit
    here: the patch is what ``.github/workflows/release.yml`` applies, so a patch that stopped
    applying must fail this fixture too.
    """
    destination = Path(os.path.realpath(destination))
    (destination / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BIN_CCODEX, destination / "bin" / "ccodex")
    completed = subprocess.run(
        ["git", "apply", "-p1", str(patch)],
        cwd=str(destination),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "the tracked mutation patch no longer applies to bin/ccodex, so the route regression it"
            f" reproduces cannot be executed: {completed.stdout}{completed.stderr}"
        )
    (destination / "bin" / "ccodex").chmod(0o755)
    for tree in ("scripts", "policy"):
        link = destination / tree
        if not link.exists():
            os.symlink(ROOT / tree, link, target_is_directory=True)
    return destination


# ---- assessment ----------------------------------------------------------------------------------


def _dotted(document: Any, path: str) -> tuple[bool, Any]:
    current = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _same(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(observed, bool):
        return isinstance(observed, bool) and isinstance(expected, bool) and observed == expected
    return observed == expected


def assess(observation: Observation) -> list[str]:
    """Every declared observation this case violated, so one run reports all of them."""
    case = observation.case
    failures: list[str] = []

    def expand(value: str) -> str:
        return value.replace(ROOT_TOKEN, str(observation.root))

    if observation.returncode != case.expect_exit:
        failures.append(f"exit {observation.returncode}, expected {case.expect_exit}")
    if case.stdout_empty and observation.stdout != "":
        failures.append(f"stdout must be empty, carries {observation.stdout[:200]!r}")
    for needle in case.stdout_present:
        if expand(needle) not in observation.stdout:
            failures.append(f"stdout is missing {expand(needle)!r}")
    for needle in case.stdout_absent:
        if expand(needle) in observation.stdout:
            failures.append(f"stdout carries the forbidden {expand(needle)!r}")
    for pattern in case.stdout_matches:
        if not re.search(pattern, observation.stdout):
            failures.append(f"stdout matches no {pattern!r}")
    for needle in case.stderr_present:
        if expand(needle) not in observation.stderr:
            failures.append(f"stderr is missing {expand(needle)!r}")
    if case.stderr_present_any and not any(
        expand(needle) in observation.stderr for needle in case.stderr_present_any
    ):
        failures.append(
            f"stderr states none of this verb's own refusal reasons {list(case.stderr_present_any)}"
        )
    for needle in case.stderr_absent:
        if expand(needle) in observation.stderr:
            failures.append(f"stderr carries the forbidden {expand(needle)!r}")
    for pattern in case.stderr_matches:
        if not re.search(pattern, observation.stderr):
            failures.append(f"stderr matches no {pattern!r}")

    if case.json_paths or case.require_finding_codes or case.forbid_finding_codes or case.canonical_json_stdout:
        try:
            report = json.loads(observation.stdout)
        except json.JSONDecodeError as exc:
            failures.append(f"stdout is not the JSON document this case asserts on: {exc}")
            return failures
        if not isinstance(report, dict):
            failures.append("stdout is JSON but not an object")
            return failures
        if case.canonical_json_stdout:
            canonical = (
                json.dumps(
                    report, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
                )
                + "\n"
            )
            if observation.stdout != canonical:
                failures.append("stdout is JSON but not the canonical form the report policy pins")
        for path, expected in sorted(case.json_paths.items()):
            found, observed = _dotted(report, path)
            if not found:
                failures.append(f"the report carries no {path}")
            elif not _same(observed, expected):
                failures.append(f"report {path} is {observed!r}, expected {expected!r}")
        codes = {
            finding.get("code")
            for finding in report.get("findings", [])
            if isinstance(finding, dict)
        }
        for code in case.require_finding_codes:
            if code not in codes:
                failures.append(f"the report carries no finding code {code!r}; it carries {sorted(codes)}")
        for code in case.forbid_finding_codes:
            if code in codes:
                failures.append(f"the report carries the forbidden finding code {code!r}")
    return failures
