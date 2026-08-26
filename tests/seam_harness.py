#!/usr/bin/env python3
"""Drive the committed ``bin/ccodex`` as a real subprocess: argv in, output and disk state out.

WHY THIS EXISTS.  Two published prereleases (v0.7.3, v0.7.4) shipped a ``ccodex sdlc`` plane that
refused itself at exit 3 from the only downloadable artifact, because the route was the shared
``uv run --script`` runner and ``runtime_admission()`` in ``scripts/ccodex_sdlc.py`` refuses every
execution shape that is not a direct isolated ``-I -B`` invocation.  ``cd3fd3d`` fixed the route and
added two tests; ``.github/workflows/release.yml`` now gates the shipped ARCHIVE.  This module is the
CHECKOUT half of the same net (gh #13's G1, wave W0 of the front-door program): it drives the
committed dispatcher over the whole lifecycle verb grammar, so a language- or route-level refactor is
a provable change rather than a bet.

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
describe the fixture rather than the developer's machine.  The one case that reads a real store is
``libraries list``, and what it asserts is a fixed heading line rather than any host-dependent count.

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

#: The top-level verbs the dispatcher routes to the reader unconditionally.
LIFECYCLE_ROUTE_VERBS = ("install", "update", "uninstall", "doctor", "recover")
#: The flags whose PRESENCE selects the lifecycle read over the gateway ``status`` verb.
LIFECYCLE_SELECTOR_FLAGS = ("--scope", "--agent", "--project")


def is_lifecycle_route(argv: tuple[str, ...]) -> bool:
    """Would ``bin/ccodex`` hand this argv to ``run_sdlc_python``?

    ``status`` is the one conditional verb: it reaches the reader only when a lifecycle selector is
    present, and is otherwise the gateway supervision verb this command has always had. The predicate
    therefore reads the whole argv rather than only its head, and it lives here rather than in the
    executing test module because both the intact-tree and regressed-tree assertions need the same
    answer about the same case.
    """
    if not argv:
        return False
    if argv[0] in LIFECYCLE_ROUTE_VERBS:
        return True
    return argv[0] == "status" and any(
        argument.split("=", 1)[0] in LIFECYCLE_SELECTOR_FLAGS for argument in argv
    )

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
#: HOW EACH MODULE NAMES ITSELF in its own refusals, which is not one string across the family. The
#: front-door wave made `ccodex install` the invocation and retired `ccodex sdlc install`; W3b renamed
#: the install module's own messages to match (seed agentic-sdlc-67c9), and the other three modules
#: still print the retired spelling because they are other waves' files. One shared f-string here would
#: have hidden exactly that split, so the map is explicit and each row states what its module EMITS --
#: the day a module is renamed, its row is what fails and names the rename.
LIFECYCLE_OWN_PREFIX = {
    "install": "error: ccodex install",
    "update": "error: ccodex sdlc update",
    "uninstall": "error: ccodex sdlc uninstall",
    "recover-apply": "error: ccodex sdlc recover --apply",
}
LIFECYCLE_REASON_SOURCES = {
    "install": "ccodex_sdlc_install.py",
    "update": "ccodex_sdlc_update.py",
    "uninstall": "ccodex_sdlc_uninstall.py",
    "recover-apply": "ccodex_sdlc_recover.py",
}


#: The selectors the four selector verbs require. Spelled once so a case cannot drift from the
#: grammar it drives.
_USER_CLAUDE = ("--scope", "user", "--agent", "claude")


def _reader_json_case(
    verb: str,
    argv: tuple[str, ...],
    extra_json: dict[str, Any] | None = None,
    stderr_present: tuple[str, ...] = (),
) -> SeamCase:
    return SeamCase(
        identifier=f"{verb}-json-is-admitted-through-the-direct-isolated-route",
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
        identifier=f"{verb}-human-render-names-the-admitted-runtime",
        argv=argv,
        expect_exit=0,
        route_sensitive=True,
        stdout_present=(f"ccodex {rendered}:", _ADMITTED_HUMAN_LINE, "checkout: ") + extra_stdout,
        stdout_absent=_HUMAN_NEVER,
        stderr_present=stderr_present,
    )


def _lifecycle_case(identifier: str, argv: tuple[str, ...], verb: str) -> SeamCase:
    """A mutating verb reaching its own module's pre-effect refusal, never a mutation.

    The declared content is platform-independent on purpose: WHICH reason a lifecycle verb states is
    a platform fact (``policy/release-smoke.v1.json`` declares those per platform, on the shipped
    artifact), while what this seam owns is that the verb reached its own module, named ITSELF,
    refused before any effect, and did not touch the fixture.  The forbidden admission text is what
    makes the case fail the moment the route regresses.

    THE EXPECTED PREFIX IS THE MODULE'S OWN, AND IT IS NOT ONE STRING ACROSS THE FAMILY: `install`
    names the surviving invocation and the other three still name the retired `ccodex sdlc <verb>`
    spelling, because they are other waves' files. `LIFECYCLE_OWN_PREFIX` carries the split per verb.
    This assertion states what the product actually emits rather than what it should; the residual is
    recorded rather than papered over, and the day a module renames itself this case is the thing that
    fails and names the rename.
    """
    return SeamCase(
        identifier=identifier,
        argv=argv,
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        stderr_present=(LIFECYCLE_OWN_PREFIX[verb],),
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
    ``unsupported ... agent``) or fell through to another plane's module would fail.
    """
    cases: list[SeamCase] = []
    for verb in ("install", "update", "uninstall"):
        for agent in ("claude", "codex"):
            cases.append(
                _lifecycle_case(
                    f"{verb}-on-the-{agent}-plane-reaches-its-module-and-refuses-before-any-effect",
                    (verb, "--scope", "user", "--agent", agent),
                    verb,
                )
            )
    return tuple(cases)


def _retired_spelling_case(
    identifier: str, argv: tuple[str, ...], present: tuple[str, ...]
) -> SeamCase:
    """A retired namespace refusing at exit 2 with the replacement invocation NAMED.

    ``stderr_present`` carries the replacement, never the bare code: exit 2 is also what every other
    usage error returns, so an exit-code assertion would keep passing if these arms fell through to
    the dispatcher's generic unknown-command text and stopped carrying the migration. Deleting either
    arm therefore fails HERE, on the message, which is the mutation this wave owes.
    """
    return SeamCase(
        identifier=identifier,
        argv=argv,
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "a retired spelling is refused by the dispatcher itself, upstream of every route and of"
            " any interpreter, so the patch cannot change it; it is a control whose subject is the"
            " migration message rather than the route"
        ),
        stdout_empty=True,
        stderr_present=present,
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    )


SEAM_CASES: tuple[SeamCase, ...] = (
    # ---- the three reader verbs, canonical JSON ------------------------------------------------
    # `inspect` is gone with the front-door unification: `status` reads one selected plane and
    # `doctor` reads the whole box, and a fourth spelling of that read was retired at the
    # dispatcher. `status` carries the two required selectors here for the same reason the product
    # requires them -- a selector-free read would be a default plane nobody typed.
    _reader_json_case("status", ("status",) + _USER_CLAUDE + ("--json",),
                      stderr_present=("selected plane: claude/user",)),
    _reader_json_case("doctor", ("doctor", "--json")),
    _reader_json_case(
        "recover-dry-run",
        ("recover", "--dry-run", "--json"),
        extra_json={"command.dry_run": True, "recovery.effect": "none"},
        stderr_present=("recovery plan",),
    ),
    # ---- the same three verbs, human render ----------------------------------------------------
    _reader_human_case("status", ("status",) + _USER_CLAUDE,
                       stderr_present=("selected plane: claude/user",)),
    _reader_human_case("doctor", ("doctor",)),
    _reader_human_case(
        "recover-dry-run",
        ("recover", "--dry-run"),
        extra_stdout=("recovery: ",),
        stderr_present=("recovery plan",),
    ),
    # ---- planted state bytes reaching the report and the approval token -------------------------
    SeamCase(
        identifier="doctor-reports-planted-lifecycle-state-bytes-it-was-given",
        argv=("doctor", "--json"),
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
        identifier="doctor-names-the-retired-operator-tools-store-and-its-manual-remedy",
        argv=("doctor", "--json"),
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
        identifier="recover-dry-run-offers-one-self-consistent-plan-digest-for-planted-state",
        argv=("recover", "--dry-run", "--json"),
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
            r" `ccodex recover --apply \1`",
        ),
        forbid_finding_codes=("runtime-admission-refused",),
        canonical_json_stdout=True,
    ),
    # ---- the three mutating verbs on both planes, refusing before any effect --------------------
    *_plane_cases(),
    _lifecycle_case(
        "recover-apply-reaches-its-module-and-refuses-before-any-effect",
        ("recover", "--apply", _UNAPPROVED_DIGEST),
        "recover-apply",
    ),
    # ---- grammar arms that are decided BEFORE the runtime is admitted --------------------------
    # These are the mutation lever's controls. The reader parses argv before it admits an
    # interpreter, so a usage error is the same document on either route; a suite where EVERY case
    # went red under the patch would not distinguish "the route regressed" from "the fixture broke".
    #
    # THE UNKNOWN-VERB CASE MOVED PLANES. With the six lifecycle verbs at the top level the
    # dispatcher enumerates every one of them, so `ccodex frobnicate` is now decided by the
    # dispatcher's own unknown-command arm and the reader's `unknown ccodex verb` arm is unreachable
    # from this surface. What replaces it as the pre-admission control is a selector error: an argv
    # that reaches the reader and is refused by its parser.
    SeamCase(
        identifier="an-unknown-top-level-command-is-a-tool-free-usage-error",
        argv=("frobnicate",),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "the dispatcher decides an unknown command before it builds any route or consults mise,"
            " so it is decided identically on both; this case is the lever's control that the"
            " regression is scoped to the lifecycle route"
        ),
        stdout_empty=True,
        stderr_present=("error: unknown command frobnicate", "usage: ccodex <command>"),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        identifier="install-without-a-scope-is-a-usage-error-naming-the-missing-selector",
        argv=("install", "--agent", "claude"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason="decided by the reader's parser before any runtime admission",
        stdout_empty=True,
        stderr_present=(
            "error: ccodex install requires an explicit --scope user|project; there is no default"
            " scope",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        # BOTH selectors are required on EVERY selector verb, not only install: with two planes live a
        # bare `uninstall` would have to pick one, and whichever it picked would remove that agent's
        # bytes on the strength of an argument nobody typed. The scope half is the same argument one
        # level out -- a run that guessed its root would touch a repository nobody named.
        identifier="uninstall-without-an-agent-is-a-usage-error-and-never-a-default-plane",
        argv=("uninstall", "--scope", "user"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "the reader parses argv before it admits a runtime, so a missing selector is decided on"
            " either route; it is a control, and its subject is the grammar rather than the route"
        ),
        stdout_empty=True,
        stderr_present=(
            "error: ccodex uninstall requires an explicit --agent claude|codex; there is no"
            " default agent",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback", "no installer ownership document"),
    ),
    SeamCase(
        identifier="an-unadmitted-agent-is-a-usage-error-naming-the-admitted-planes",
        argv=("install", "--scope", "user", "--agent", "gemini"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "an unadmitted selector is refused by the reader's parser before any runtime admission, so"
            " it is decided identically on either route; it is the positive control for the six"
            " admitted-plane cases above"
        ),
        stdout_empty=True,
        stderr_present=(
            "error: unsupported ccodex install agent: 'gemini'; the admitted agents are"
            " claude, codex",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        # A flag that contradicts its own scope is exit 2 BEFORE any filesystem resolution, and the
        # refusal states the doctrine rather than citing it: project scope is copy-only, so `--mode`
        # has no admissible value there.
        identifier="a-mode-request-at-project-scope-is-a-grammar-refusal-carrying-the-three-reasons",
        argv=("install", "--scope", "project", "--agent", "claude", "--mode", "link"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "a scope/flag contradiction is decided by the reader's parser before any runtime"
            " admission and before any filesystem resolution, so it is identical on both routes"
        ),
        stdout_empty=True,
        stderr_present=(
            "error: ccodex install --mode is admitted only with --scope user",
            "a link embeds a user-specific absolute path",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    SeamCase(
        identifier="a-project-flag-at-user-scope-is-a-grammar-refusal",
        argv=("status", "--scope", "user", "--agent", "claude", "--project", "/nonexistent"),
        expect_exit=2,
        route_sensitive=False,
        insensitivity_reason=(
            "the other half of the scope/flag pair, decided by the same parser before any runtime"
            " admission; it is the positive control that the pair is checked in both directions"
        ),
        stdout_empty=True,
        stderr_present=(
            "error: ccodex status --project is admitted only with --scope project",
        ),
        stderr_absent=("expected direct -I -B execution", "Traceback"),
    ),
    # ---- the ratified grammar this release parses but does not yet serve (exit 3, by name) -------
    # This is the alternative to the two dishonest options: silently ignoring the flag (an operator who
    # typed `--scope project` gets their user home) or refusing it as a usage error (telling them they
    # mistyped what the ratified grammar contains). Deleting it makes this case fail on the MESSAGE,
    # which is where the refusal name lives.
    #
    # `--mode` AND `--dry-run` USED TO BE HERE and are now WIRED (W3b of the same seed). Their cases
    # moved below and inverted: what they assert now is that each flag reached its module -- a refusal
    # only the module can produce for `--mode link`, and a preview the reader could not have rendered --
    # and that the two retired refusal names are GONE from the product rather than kept as aliases.
    # ---- project scope, wired in W4 and proven to REACH each module ----------------------------
    #
    # The case that used to sit here asserted `project-scope-not-yet-wired`. It is GONE rather than
    # kept as an alias, for the reason the mode and dry-run cases below record: a token that still
    # answered would say a wired surface is unwired. What replaces it is the same shape those two took
    # -- a refusal only the module (or, for a read, only the reader's own ladder) can produce.
    SeamCase(
        identifier="a-project-root-request-reaches-the-install-module-and-its-ladder-names-the-refusal",
        argv=("install", "--scope", "project", "--agent", "claude", "--project", "/nonexistent/project"),
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        # ONLY THE MODULE CAN PRODUCE THIS. The reader admits the pair as grammar and forwards it; the
        # install module resolves it through the shared ladder and refuses the absent root by name,
        # BEFORE it reads the acquisition plane -- which is why an empty host answers about the root
        # rather than about a missing candidate. The case fails if either flag is dropped, if the reader
        # refuses the scope itself, or if a user-scope plane is silently activated instead.
        stderr_present=(
            LIFECYCLE_OWN_PREFIX["install"],
            "unresolvable-project-root",
            "/nonexistent/project",
        ),
        stderr_absent=(
            "project-scope-not-yet-wired",
            "admits exactly",
            "expected direct -I -B execution",
            "Traceback",
        ),
    ),
    SeamCase(
        identifier="a-project-scope-with-no-named-root-walks-up-from-the-working-directory",
        argv=("uninstall", "--scope", "project", "--agent", "claude"),
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        # The OTHER rung of the ladder, driven through the whole seam: no `--project`, so the module
        # walks up from the working directory this runner hands it -- a scratch cell with no `.git`
        # anywhere above it -- and names the flag that would resolve one. A module that defaulted to the
        # user plane would answer about the operator's home instead, which is the substitution the
        # refusal exists to prevent.
        # THE MODULE'S OWN PREFIX IS DELIBERATELY NOT ASSERTED HERE, and that is a finding rather than
        # an omission: `LIFECYCLE_OWN_PREFIX["uninstall"]` is `error: ccodex sdlc uninstall`, the RETIRED
        # namespace the dispatcher itself refuses (W3a residual 4 records that those modules still print
        # it). This wave's own refusals name the surviving surface instead, so what proves the module
        # produced this line is its own closing sentence -- the reader dispatches for `uninstall` and
        # never resolves a root, and it has no "Nothing was removed" to print.
        stderr_present=(
            "error: ccodex uninstall --scope project refused this root",
            "unresolvable-project-root",
            "--project PATH",
            "Nothing was removed",
        ),
        stderr_absent=(
            "project-scope-not-yet-wired",
            "admits exactly",
            "expected direct -I -B execution",
            "Traceback",
        ),
    ),
    SeamCase(
        identifier="a-project-scope-read-resolves-its-own-root-and-refuses-an-absent-one",
        argv=("status", "--scope", "project", "--agent", "claude", "--project", "/nonexistent/project", "--json"),
        expect_exit=3,
        route_sensitive=True,
        # A READ resolves the root ITSELF -- it dispatches to no module -- so this refusal is the
        # reader's own, and stdout stays empty rather than carrying a whole-host report about a
        # repository that does not exist.
        stdout_empty=True,
        stderr_present=(
            "error: ccodex status --scope project cannot read",
            "unresolvable-project-root",
        ),
        stderr_absent=(
            "project-scope-not-yet-wired",
            "usage: ccodex status",
            "expected direct -I -B execution",
            "Traceback",
        ),
    ),
    # ---- the two flags W3b wired, each proven to REACH its module ------------------------------
    SeamCase(
        identifier="a-mode-link-request-reaches-its-module-and-is-refused-for-this-payload-class",
        argv=("install",) + _USER_CLAUDE + ("--mode", "link"),
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        # THIS REFUSAL IS ONLY REACHABLE THROUGH THE MODULE. The reader admits `--mode link` at user
        # scope as grammar, forwards it, and the install module refuses it against the payload class it
        # would activate -- so the case fails if the flag is dropped, refused by the reader, or
        # silently downgraded to a copy. The absent tokens are the two names the retired unwired
        # refusals carried: an alias that still answered would say a wired surface is unwired.
        stderr_present=(
            LIFECYCLE_OWN_PREFIX["install"],
            "mode-forbidden-for-acquired-payload",
            "copies and never links",
        ),
        stderr_absent=(
            "mode-not-yet-wired",
            "expected direct -I -B execution",
            "Traceback",
        ),
    ),
    SeamCase(
        identifier="an-admitted-mode-request-is-forwarded-and-the-module-refuses-on-its-own-terms",
        argv=("install",) + _USER_CLAUDE + ("--mode", "copy"),
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        # An admitted mode changes nothing about WHY an empty host refuses: the module still reaches its
        # own payload admission and names it. What this case adds is that the vector carrying `--mode`
        # is one the module ADMITS -- a module that rejected the shape would answer "admits exactly".
        stderr_present=(LIFECYCLE_OWN_PREFIX["install"], "no acquired candidate is available"),
        stderr_absent=(
            "mode-not-yet-wired",
            "admits exactly",
            "expected direct -I -B execution",
            "Traceback",
        ),
    ),
    SeamCase(
        identifier="a-dry-run-request-reaches-its-module-and-previews-instead-of-refusing-unwired",
        argv=("uninstall",) + _USER_CLAUDE + ("--dry-run",),
        expect_exit=3,
        route_sensitive=True,
        stdout_empty=True,
        # An empty host has no plane to preview, so the ladder runs out of rungs and names both rungs
        # it looked for -- the same refusal the flagless vector gets, which is correct: a preview of
        # nothing is still nothing. What this case owns is that the flag is FORWARDED and admitted
        # rather than refused by name, and that the retired token is gone.
        stderr_present=(LIFECYCLE_OWN_PREFIX["uninstall"], "no installer ownership document"),
        stderr_absent=(
            "dry-run-not-yet-wired",
            "admits exactly",
            "expected direct -I -B execution",
            "Traceback",
        ),
    ),
    # ---- the two retired namespaces ------------------------------------------------------------
    _retired_spelling_case(
        "the-retired-bundle-install-spelling-names-its-replacement-invocation",
        ("bundle", "install", "--agent", "claude"),
        (
            "error: `ccodex bundle install` is retired. The lifecycle verb is now top-level:",
            "ccodex install --scope user --agent <claude|codex>",
        ),
    ),
    _retired_spelling_case(
        "the-retired-bundle-status-spelling-names-its-replacement-invocation",
        ("bundle", "status", "--agent", "claude"),
        (
            "error: `ccodex bundle status` is retired. The lifecycle verb is now top-level:",
            "ccodex status --scope user --agent <claude|codex>",
        ),
    ),
    _retired_spelling_case(
        "a-bare-retired-bundle-namespace-names-all-three-replacements",
        ("bundle",),
        (
            "error: `ccodex bundle` is retired. The lifecycle verbs are now top-level:",
            "ccodex install   --scope user --agent <claude|codex>",
            "ccodex uninstall --scope user --agent <claude|codex>",
        ),
    ),
    _retired_spelling_case(
        "the-retired-sdlc-read-spelling-names-both-replacement-verbs",
        ("sdlc", "status"),
        (
            "error: `ccodex sdlc status` is retired. Read verbs are now top-level:",
            "ccodex status --scope user --agent <claude|codex>   (per plane)",
            "ccodex doctor                                       (whole box)",
        ),
    ),
    _retired_spelling_case(
        "the-retired-sdlc-inspect-spelling-maps-onto-the-two-surviving-read-verbs",
        ("sdlc", "inspect", "--json"),
        (
            "error: `ccodex sdlc inspect` is retired. Read verbs are now top-level:",
            "ccodex doctor",
        ),
    ),
    _retired_spelling_case(
        "the-retired-sdlc-mutating-spelling-names-its-replacement-invocation",
        ("sdlc", "uninstall", "--host", "claude"),
        (
            "error: `ccodex sdlc uninstall` is retired. The lifecycle verb is now top-level:",
            "ccodex uninstall --scope user --agent <claude|codex>",
        ),
    ),
    _retired_spelling_case(
        "the-retired-sdlc-recover-spelling-names-both-recover-forms",
        ("sdlc", "recover", "--dry-run"),
        (
            "error: `ccodex sdlc recover` is retired. The recover verb is now top-level:",
            "ccodex recover --dry-run [--json]",
            "ccodex recover --apply <plan-sha256>",
        ),
    ),
    _retired_spelling_case(
        "a-bare-retired-sdlc-namespace-names-the-whole-new-surface",
        ("sdlc",),
        (
            "error: `ccodex sdlc` is retired. Its verbs are now top-level:",
            "ccodex install|status|update|uninstall --scope <user|project> --agent <claude|codex>",
            "ccodex recover --dry-run [--json] | --apply <plan-sha256>",
        ),
    ),
    SeamCase(
        identifier="top-level-help-names-the-whole-new-verb-table-and-both-retired-spellings",
        argv=("--help",),
        expect_exit=0,
        route_sensitive=False,
        insensitivity_reason=(
            "help is tool-free and answered by the dispatcher before mise, any trust step, and any"
            " route, so the patch cannot reach it; it is a control"
        ),
        stdout_present=(
            "usage: ccodex <command>",
            "install --scope <user|project> --agent <claude|codex>",
            "uninstall --scope <user|project> --agent <claude|codex>",
            "doctor [--json]",
            "recover --apply <plan-sha256>",
            "`ccodex bundle <verb>` and `ccodex sdlc <verb>` are refused at exit 2",
        ),
        stdout_absent=("Traceback", "sdlc install --host", "profile", "refresh"),
    ),
    # ---- boundaries the dispatcher owns, upstream of any interpreter ---------------------------
    SeamCase(
        identifier="an-untrusted-root-refuses-the-lifecycle-route-naming-this-trees-own-remedy",
        argv=("status",) + _USER_CLAUDE + ("--json",),
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
        # RECLASSIFIED 1 -> 3 in the wave that landed the verb table (the W0 seam's own finding):
        # nothing was attempted, no tool resolved, no route built, so this is a precondition boundary
        # declining before any effect rather than a failure of the tool. Class 1 stays reserved for
        # the dispatcher's OWN unexpected internal failures.
        identifier="a-probe-failure-that-is-not-a-trust-refusal-refuses-as-unreadable",
        argv=("status",) + _USER_CLAUDE + ("--json",),
        expect_exit=3,
        route_sensitive=False,
        insensitivity_reason=(
            "the toolchain probe is upstream of both routes; this is the trust case's discriminator,"
            " proving the refusal above is classified from the probe's own text"
        ),
        mise="unreadable",
        stdout_empty=True,
        stderr_present=(f"refused: mise cannot read {ROOT_TOKEN}:", "the fixture probe declined"),
        stderr_absent=("not trusted", "mise trust", "expected direct -I -B execution"),
    ),
    SeamCase(
        identifier="libraries-list-still-reaches-the-shared-uv-runner",
        # This case replaced `bundle status`, which was the lever's shared-uv-runner control until
        # `ccodex bundle` became a refusal. `libraries` is the surviving read verb on that route, so
        # the control's SUBJECT is unchanged: the stub's uv-run emulation works, and the regression is
        # confined to the lifecycle route.
        argv=("libraries", "list"),
        expect_exit=0,
        route_sensitive=False,
        insensitivity_reason=(
            "the libraries route is ALREADY the shared uv runner, so the patch cannot change it; it"
            " is the lever's positive control that the stub's uv-run emulation works and that the"
            " regression is confined to the lifecycle route"
        ),
        stdout_present=(
            "External skill libraries reachable through their own front doors.",
            "Nothing below is installed by `lifecycle:install`",
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


def stub_dispatcher_environment(
    cell: Path,
    *,
    root: Path | None = None,
    interpreter: Path | None = None,
    probe: str = "trusted",
    home: Path | None = None,
    state: Path | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """One allowlist environment in which the COMMITTED ``bin/ccodex`` can be driven as a process.

    WHY THE IN-PROCESS SUITES NEED THIS. ``bin/ccodex`` refuses an untrusted root before any route,
    and the trust it wants is scoped to the REAL operator ``HOME`` -- a fact an isolated test home can
    never carry without a persistent operator mutation. Every suite that wanted the real dispatcher
    therefore drove the reader directly under ``-I -B`` and documented the gap. This function closes
    it: the recording stub ``mise`` stands at exactly that boundary, serving both routes the
    dispatcher can build, so a suite gets the real argv-to-decision path instead of a hand-built
    approximation of it.

    Callers run ``[BIN_CCODEX, *argv]`` with the returned environment. The stub's argv log lands at
    ``cell / "mise-argv.log"`` and is readable afterwards, which is what lets a caller assert WHICH
    route the dispatcher built rather than only what came out of it.

    ``extra`` is merged last, so a suite may add the one or two values its own fixture needs
    (``CODEX_HOME``, a poisoned ``PYTHONPATH``) without reopening the allowlist to ``os.environ``.
    """
    cell = Path(cell)
    resolved_home = Path(home) if home is not None else cell / "home"
    resolved_state = Path(state) if state is not None else cell / "state"
    stub_bin = cell / "stub-bin"
    # The STATE ROOT is deliberately not created. Several callers assert that a read verb left it
    # absent, which is a real no-effect observation this helper must not spend on their behalf; a
    # caller that needs the directory plants it itself, as the fixture writers below do.
    for directory in (resolved_home, stub_bin):
        directory.mkdir(parents=True, exist_ok=True)
    write_stub_mise(
        stub_bin,
        root=Path(os.path.realpath(root or ROOT)),
        interpreter=Path(os.path.realpath(interpreter or Path(sys.executable))),
        log=cell / "mise-argv.log",
        probe=probe,
    )
    environment = {
        "PATH": os.pathsep.join(
            [str(stub_bin), str(dispatcher_utilities_path(cell / "utilities"))]
        ),
        "HOME": str(resolved_home),
        "XDG_STATE_HOME": str(resolved_state),
        "XDG_DATA_HOME": str(cell / "data"),
        "LANG": "C",
        "LC_ALL": "C",
        # The regressed route runs the reader WITHOUT ``-B``, exactly as ``uv run`` does, so it writes
        # bytecode; sending that cache into the fixture keeps the tree under test clean.
        "PYTHONPYCACHEPREFIX": str(cell / "pycache"),
    }
    environment.update(extra or {})
    return environment


def stub_mise_argv(cell: Path) -> tuple[str, ...]:
    """Every argv the stub ``mise`` in this cell was called with, in order."""
    log = Path(cell) / "mise-argv.log"
    return tuple(log.read_text(encoding="utf-8").splitlines()) if log.exists() else ()


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


#: What the stub launcher prints, so the gateway assertion reads a verb rather than a health probe.
GATEWAY_STUB_MARKER = "GATEWAY-VERB:"


def build_stub_launcher_tree(destination: Path) -> Path:
    """A distribution root whose ``scripts/opencodex-claude.sh`` is a recording stub.

    THE DISPATCHER SELF-LOCATES ITS ROOT as the physical parent of its own ``bin/``, which is what
    makes this possible without touching the checkout: a copy of ``bin/ccodex`` placed here resolves
    ``$root/scripts/opencodex-claude.sh`` to the stub below, so the gateway route can be OBSERVED
    instead of executed. Nothing under this tree is the real launcher, and the real one is never run
    by any test -- it would start a gateway process.

    ``scripts/`` is a real directory rather than a symlink to the checkout's, precisely because the
    stub has to live inside it. The reader is unreachable from here on purpose: a case that needed
    both the stub launcher and the real reader would be asserting two planes at once.
    """
    destination = Path(os.path.realpath(destination))
    (destination / "bin").mkdir(parents=True, exist_ok=True)
    (destination / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BIN_CCODEX, destination / "bin" / "ccodex")
    (destination / "bin" / "ccodex").chmod(0o755)
    launcher = destination / "scripts" / "opencodex-claude.sh"
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '{GATEWAY_STUB_MARKER}%s\\n' \"$1\"\n"
        'shift\n'
        "printf 'GATEWAY-ARGV:%s\\n' \"$*\"\n",
        encoding="utf-8",
        newline="\n",
    )
    launcher.chmod(0o755)
    return destination


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
