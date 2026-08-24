#!/usr/bin/env python3
"""Read-only checkout-development evidence behind ``ccodex sdlc``.

The installed dispatcher invokes this file with its install-bound, UV-managed Python 3.12.11 using
``-I -B``.  Its reader verbs are intentionally not a lifecycle surface: they read existing state,
never create or repair it, and render one closed semantic report in either human or canonical JSON
form.

This file also owns the closed grammar of the three mutating lifecycle verbs (``install --host
claude``, ``update``, ``uninstall``), and it owns nothing else about them.  It parses them, refuses
them by name, or hands the admitted vector to one per-verb module loaded by absolute file path; it
performs no lifecycle mutation and acquires no writer authority of its own.
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import Any


REPORT_SCHEMA_VERSION = "ccodex-sdlc-read-report/v1"
POLICY_SCHEMA_VERSION = "ccodex-sdlc-read-report-policy/v1"
POLICY_NAME = "ccodex-sdlc-read-report.v1.json"
EXPECTED_CHECKOUT = {
    "certification_claim": "none",
    "plane": "checkout-development",
    "public_channel": None,
    "release_topology_adr_status": "proposed",
    "version": "0.7.4",
}
READER_VERBS = ("inspect", "status", "doctor", "recover")
# The three mutating lifecycle verbs. This file stays a reader: it parses the closed grammar and
# then either refuses or hands the admitted vector to ONE named per-verb module loaded by absolute
# file path.  It performs no lifecycle mutation itself and acquires no writer authority.  The
# modules are separate tickets and are absent today, so every mutating verb refuses BY NAME at
# exit 3 -- a clean refusal before any effect -- rather than raising.  `update` is the decided
# spelling; `refresh` is not this plane's verb, and there is no verb family beyond these three.
LIFECYCLE_VERBS = {
    "install": "ccodex_sdlc_install",
    "update": "ccodex_sdlc_update",
    "uninstall": "ccodex_sdlc_uninstall",
}
# `install` requires an explicit host. There is no default and no wildcard.
LIFECYCLE_HOSTS = ("claude",)
# `recover` keeps its reader form AND gains exactly one mutating form (Decision 91: recovery stays
# inside this closed namespace rather than becoming a fifth verb).  THE APPROVAL IS THE DIGEST:
# `recover --dry-run` derives a digest-bound plan and renders that digest, and `recover --apply
# <plan-sha256>` approves that one exact plan.  The mutating form dispatches to its own per-verb
# module by absolute path exactly as the three lifecycle verbs do; it is deliberately NOT a member of
# LIFECYCLE_VERBS, because `recover` is still a reader verb whose default form reads.
RECOVER_APPLY_FLAG = "--apply"
RECOVER_MODULE = "ccodex_sdlc_recover"
LIFECYCLE_MODULES = {**LIFECYCLE_VERBS, "recover": RECOVER_MODULE}
# Re-expressed from that module so a drifted plan shape is DECLINED by name rather than silently
# digested as though nothing changed; `load_recovery_planner` compares this against the module's own
# constant and declines the whole digest dimension when they disagree.
RECOVERY_PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-recovery-plan@1"

# ---- host-level lifecycle readiness ----------------------------------------------------------
# The host-level half of pre-effect readiness is READ here and nowhere else (agentic-sdlc-9857,
# spec Decision 8): selected payload versus activated version, distribution-activation receipt
# presence and seal validity, interrupted transitions, and the contract's declared
# incompatibilities against the observed host.  Nothing below repairs, networks, executes a host,
# resolves a version, or acquires writer authority, and every location is a parameter so a test
# points the observation at its own plane instead of at the operator's.
STATE_PLANE_DIRECTORY = "agentic-sdlc"
ACQUISITION_PLANE = ("acquisition", "receipts")
ACTIVATION_PLANE = ("activation", "receipts")
ACQUISITION_RECEIPT_SCHEMA = "release-candidate-acquisition-receipt/v1"
ACQUISITION_TERMINAL_PHASE = "installed-unselected"
ACQUISITION_SELECTION = "absent"
ACTIVATION_VALIDATOR_MODULE = "distribution_activation_receipt"
# Re-expressed from that module so a drifted vocabulary is REFUSED by name rather than silently
# reinterpreted; `load_activation_validator` compares these against the module's own constants and
# declines the whole dimension when they disagree.  A guessed matrix would read as an observation.
EXPECTED_RECEIPT_KIND = "distribution-activation"
EXPECTED_RECEIPT_VOCABULARIES = {
    "EFFECT_STATES": ("complete", "none", "partial", "unknown"),
    "OPERATIONS": ("install", "uninstall", "update"),
    "TERMINAL_PHASES": ("activated", "activated-partial", "not-activated", "retired", "unknown"),
    "VERSION_SOURCES": ("adapter-readback", "archive-manifest", "request"),
}
# A transition that stopped between its phases. `unknown` is included on purpose: a receipt that
# cannot state its own effect is exactly the case an operator must be told about.
INTERRUPTED_EFFECT_STATES = ("partial", "unknown")
INTERRUPTED_TERMINAL_PHASES = ("activated-partial", "unknown")
ACTIVE_TERMINAL_PHASES = ("activated", "activated-partial")
# `request` is the refused member of that closed set: a requested version is what the caller asked
# for, never what an adapter read back, so it never becomes an activated version here.
PROVEN_VERSION_SOURCES = ("adapter-readback", "archive-manifest")
# THE PLANE'S ONE ACTIVE STATEMENT, and the two facts that keep a healthy history from reading as a
# defect. `ccodex sdlc install` writes this pointer and `ccodex sdlc update` replaces it, while the
# receipt the update replaced is RETAINED under its own id -- deliberately, so a kill mid-update
# leaves a readable prior statement. Both documents therefore coexist on a healthy plane, and a
# reader that counted every filed receipt as a current activation would report the retention as an
# ambiguity. Two independent facts resolve it, and neither one is invented here: the pointer names
# the current receipt, and an update's own `supersedes` ancestor names the receipt it replaced.
ACTIVE_POINTER_NAME = "active-receipt.json"
SUPERSEDES_RELATION = "supersedes"
# The pointer's own opaque locator. It is a fixed name this reader already knows, so it carries no
# operator content and is spelled out rather than digested.
ACTIVE_POINTER_LOCATOR = "activation-plane://active-receipt"
# A receipt id is CORRELATED here, so it is admitted only in a bounded closed shape, exactly as
# `safe_version` bounds a version. The family's own token rule is lowercase letters, ASCII digits,
# and interior hyphens; the charset is written out because `\w` and `\d` admit Unicode, and a
# receipt id spelled in Arabic-Indic digits would read as the same identity while comparing unequal.
MAX_RECEIPT_ID_CHARS = 128
_RECEIPT_ID_CHARACTERS = "0123456789abcdefghijklmnopqrstuvwxyz-"
# One receipt is a few kilobytes. The ceiling means an oversized or truncated file is NAMED as
# unreadable instead of being read into this process, and the document bound means an unbounded
# directory cannot turn a bounded read into a scan.
MAX_PLANE_DOCUMENT_BYTES = 65536
MAX_PLANE_DOCUMENTS = 64
MAX_FINDING_MESSAGE_CHARS = 240
MAX_VERSION_CHARS = 64
# Two reasons a finding maps onto a code by EXACT equality rather than by searching the prose: a
# substring test over a message would silently reclassify the day an `strerror` happened to contain
# the word, and these two states are not "unreadable".
PLANE_SYMLINK_REASON = "is a symlink, which this reader reports instead of following"
PLANE_OVERFULL_REASON = (
    f"holds more than {MAX_PLANE_DOCUMENTS} documents, so this reader read only the first "
    f"{MAX_PLANE_DOCUMENTS} of them"
)
# Written out rather than spelled `[0-9a-f]`-by-regex-class shorthand: `\d` admits the Arabic-Indic
# `٩`, so a digest spelled in it would read as the same value while comparing unequal to it.
_HEX_CHARACTERS = "0123456789abcdef"
_VERSION_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.+-"
_DISPLAY_ESCAPES = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


class UsageError(ValueError):
    pass


class LifecycleRefusal(RuntimeError):
    """A mutating lifecycle verb declined BEFORE any effect could occur (exit class 3)."""


class LifecycleUnknownEffect(RuntimeError):
    """A per-verb module already executed, so no absence of effect can be claimed (exit class 4)."""


class ReportInvariantError(RuntimeError):
    pass


class _Unsupplied:
    """The third state of an injected location: nobody named one at all.

    ``None`` means "a location was named and this reader must treat it as absent"; ``UNSUPPLIED``
    means "no caller named one, so use the layout's own convention".  Supplied-but-missing and
    not-supplied are different inputs with different recorded reasons, and collapsing them would let
    a caller that named nothing read as a caller that named an absence.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "UNSUPPLIED"


UNSUPPLIED = _Unsupplied()


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON value {value!r}")


def strict_json_document(content: bytes, label: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            content.decode("utf-8"), object_pairs_hook=_reject_duplicate, parse_constant=_reject_constant
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ReportInvariantError(f"invalid JSON in {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReportInvariantError(f"JSON object required: {label}")
    return value


def canonical_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"


def _exact_keys(value: object, expected: list[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ReportInvariantError(f"{label} fields must be exactly {expected}")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    _exact_keys(
        policy,
        [
            "canonical_serialization",
            "field_vocabularies",
            "report_schema_version",
            "report_top_level_fields",
            "schema_version",
            "vocabularies",
        ],
        "read-report policy",
    )
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ReportInvariantError("read-report policy schema version is invalid")
    if policy.get("report_schema_version") != REPORT_SCHEMA_VERSION:
        raise ReportInvariantError("read-report policy report schema version is invalid")
    canonical = _exact_keys(
        policy["canonical_serialization"],
        ["allow_nonfinite", "ensure_ascii", "indent", "separators", "sort_keys", "trailing_newline"],
        "read-report canonical serialization",
    )
    if canonical != {
        "allow_nonfinite": False,
        "ensure_ascii": True,
        "indent": None,
        "separators": [",", ":"],
        "sort_keys": True,
        "trailing_newline": True,
    }:
        raise ReportInvariantError("read-report policy canonical serialization is invalid")
    top_level = policy["report_top_level_fields"]
    expected_top_level = [
        "schema_version",
        "command",
        "checkout",
        "runtime",
        "operator_tools",
        "bundle",
        "recovery",
        "future_dimensions",
        "findings",
        "overall",
    ]
    if top_level != expected_top_level or len(top_level) != len(set(top_level)):
        raise ReportInvariantError("read-report policy top-level vocabulary is invalid")
    field_vocabularies = policy["field_vocabularies"]
    expected_fields = {
        "bundle": ["entries", "findings", "recovery", "state", "state_paths"],
        "checkout": ["certification_claim", "plane", "public_channel", "release", "release_topology_adr_status", "version"],
        "command": ["dry_run", "verb"],
        "finding": ["code", "component", "message", "path"],
        "future_dimensions": ["activation", "release", "waves"],
        "overall": ["exit_class", "state"],
        "projection_entry": ["name", "path", "state"],
        "recovery": ["effect", "proposals", "state"],
        "recovery_item": ["action", "component", "path", "state"],
        "runtime": ["interpreter", "isolated", "state", "version"],
    }
    if field_vocabularies != expected_fields:
        raise ReportInvariantError("read-report policy field vocabulary is invalid")
    vocabularies = policy["vocabularies"]
    expected_vocabularies = {
        "command_verbs",
        "component_states",
        "entry_states",
        "exit_classes",
        "finding_codes",
        "finding_components",
        "overall_states",
        "recovery_actions",
        "recovery_effects",
        "recovery_states",
        "recovery_item_states",
        "runtime_states",
    }
    if not isinstance(vocabularies, dict) or set(vocabularies) != expected_vocabularies:
        raise ReportInvariantError("read-report policy value vocabulary is invalid")
    for key, values in vocabularies.items():
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
            raise ReportInvariantError(f"read-report policy {key} must be a non-empty string list")
        if len(values) != len(set(values)):
            raise ReportInvariantError(f"read-report policy {key} must not repeat values")


def load_policy(root: Path) -> dict[str, Any]:
    path = root / "policy" / POLICY_NAME
    if path.is_symlink() or not path.is_file():
        raise ReportInvariantError(f"read-report policy is unavailable: {path}")
    raw = path.read_bytes()
    policy = strict_json_document(raw, path)
    validate_policy(policy)
    if raw != canonical_json(policy).encode("utf-8"):
        raise ReportInvariantError("read-report policy must use canonical JSON")
    return policy


def load_release_contract(root: Path) -> dict[str, Any]:
    """Read the tracked release contract once, so the identity and the compatibility declaration
    are two views of ONE observed document rather than two reads that could disagree."""
    path = root / "policy" / "release-contract.v1.json"
    if path.is_symlink() or not path.is_file():
        raise ReportInvariantError(f"release contract is unavailable: {path}")
    return strict_json_document(path.read_bytes(), path)


def checkout_identity(contract: dict[str, Any]) -> dict[str, Any]:
    # The version is INTERPOLATED from the pin above, never spelled again here: a second literal is
    # a second place a bump has to reach, and the one that rots quotes the version being REPLACED --
    # so the message would name 0.7.4 while refusing a 0.7.5 contract, pointing a reader at the
    # wrong side of the mismatch (agentic-sdlc-3174).
    checkout = contract.get("checkout")
    if contract.get("schema_version") != "release-contract/v1" or checkout != EXPECTED_CHECKOUT:
        raise ReportInvariantError(
            "release contract does not establish the checkout-development "
            f"{EXPECTED_CHECKOUT['version']} identity"
        )
    return {
        "certification_claim": checkout["certification_claim"],
        "plane": checkout["plane"],
        "public_channel": checkout["public_channel"],
        "release": None,
        "release_topology_adr_status": checkout["release_topology_adr_status"],
        "version": checkout["version"],
    }


def parse_lifecycle_host(verb: str, rest: list[str]) -> str | None:
    """Resolve the host of one mutating lifecycle verb, or refuse the spelling as a grammar error.

    Every echoed caller token is rendered with ``!r`` so a control character, an escape sequence,
    or a bidirectional override in an argument cannot forge a line of this command's own output.
    Not-supplied, supplied-without-a-value, and supplied-with-an-unsupported-value are three
    distinct refusals, because collapsing them hides which half of the invocation was wrong.
    """
    if verb != "install":
        if rest:
            raise UsageError(f"ccodex sdlc {verb} accepts no arguments: {rest[0]!r}")
        return None
    if not rest:
        raise UsageError("ccodex sdlc install requires an explicit --host claude; there is no default host")
    if rest[0] != "--host":
        if rest[0].startswith("--host="):
            raise UsageError("ccodex sdlc install spells its host as two arguments: --host claude")
        raise UsageError(f"unknown ccodex sdlc install argument: {rest[0]!r}")
    if len(rest) == 1:
        raise UsageError("ccodex sdlc install --host was supplied without a host value")
    if len(rest) > 2:
        raise UsageError(f"ccodex sdlc install accepts exactly --host claude: {rest[2]!r}")
    host = rest[1]
    if host not in LIFECYCLE_HOSTS:
        raise UsageError(f"unsupported ccodex sdlc install host: {host!r}; the only admitted host is claude")
    return host


def parse_recover_apply(rest: list[str]) -> str:
    """Resolve the plan digest of ``recover --apply``, or refuse the spelling as a grammar error.

    Not-supplied, supplied-without-a-value, and supplied-with-an-unusable-value are three distinct
    refusals: collapsing them hides which half of the invocation was wrong.  The digest is tested by
    membership in an explicit lowercase hex alphabet, never by a regex digit class -- ``\\d`` admits
    the Arabic-Indic ``٩``, so a digest spelled in it would read as the same value while comparing
    unequal to every plan this command could derive.
    """
    if len(rest) == 1:
        raise UsageError(
            f"ccodex sdlc recover {RECOVER_APPLY_FLAG} was supplied without the plan digest it approves"
        )
    if len(rest) > 2:
        raise UsageError(
            f"ccodex sdlc recover {RECOVER_APPLY_FLAG} accepts exactly one plan digest: {rest[2]!r}"
        )
    digest = rest[1]
    if len(digest) != 64 or any(character not in _HEX_CHARACTERS for character in digest):
        raise UsageError(
            f"ccodex sdlc recover {RECOVER_APPLY_FLAG} requires the 64-character lowercase"
            f" hexadecimal digest of one derived plan: {digest!r}"
        )
    return digest


def parse_command(argv: list[str]) -> tuple[str, bool, bool, str | None]:
    if argv in (["-h"], ["--help"], ["help"]):
        raise UsageError("help")
    if not argv:
        raise UsageError(
            "ccodex sdlc needs inspect, status, doctor, recover --dry-run, install --host claude, update, or uninstall"
        )
    verb = argv[0]
    rest = argv[1:]
    if verb in LIFECYCLE_VERBS:
        # A mutating verb carries no reader flag: it is never a dry run and never renders a report.
        return verb, False, False, parse_lifecycle_host(verb, rest)
    if verb not in READER_VERBS:
        raise UsageError(f"unknown ccodex sdlc verb: {verb!r}")
    if verb == "recover":
        if rest == ["--dry-run"]:
            return verb, True, False, None
        if rest == ["--dry-run", "--json"]:
            return verb, True, True, None
        # The fourth element carries the ONE argument an admitted vector forwards to a per-verb
        # module: the install host for `install`, and the approved plan digest here.  A dry run
        # forwards nothing and therefore carries None, which is what keeps the two forms distinct.
        if rest and rest[0] == RECOVER_APPLY_FLAG:
            return verb, False, False, parse_recover_apply(rest)
        if rest and rest[0].startswith(f"{RECOVER_APPLY_FLAG}="):
            raise UsageError(
                "ccodex sdlc recover spells its approval as two arguments:"
                f" {RECOVER_APPLY_FLAG} <plan-sha256>"
            )
        raise UsageError(
            "ccodex sdlc recover requires exactly --dry-run, optionally followed by --json, or"
            f" {RECOVER_APPLY_FLAG} <plan-sha256>"
        )
    if rest == []:
        return verb, False, False, None
    if rest == ["--json"]:
        return verb, False, True, None
    raise UsageError(f"ccodex sdlc {verb} accepts only optional --json")


def usage() -> str:
    return (
        "usage: ccodex sdlc inspect [--json]\n"
        "       ccodex sdlc status [--json]\n"
        "       ccodex sdlc doctor [--json]\n"
        "       ccodex sdlc recover --dry-run [--json]\n"
        "       ccodex sdlc recover --apply <plan-sha256>\n"
        "       ccodex sdlc install --host claude\n"
        "       ccodex sdlc update\n"
        "       ccodex sdlc uninstall\n\n"
        "inspect, status, doctor, and recover --dry-run read checkout-development ownership and\n"
        "recovery evidence without installing, updating, uninstalling, following, or changing state.\n"
        "`recover --dry-run` is proposal-only, requires the literal --dry-run safeguard, and renders\n"
        "the sha256 of the exact plan it derived. `recover --apply <plan-sha256>` is the one mutating\n"
        "recover form: the approval IS the digest, so it re-derives that plan from verified journal\n"
        "and receipt state and refuses by name when the re-derived digest differs, when the evidence\n"
        "does not verify, or when there is nothing to recover.\n\n"
        "install, update, and uninstall are the mutating lifecycle verbs. This reader performs no\n"
        "lifecycle mutation itself: it parses the closed grammar above and hands an admitted vector\n"
        "to one named per-verb module, refusing by name before any effect when that module is not\n"
        "present in this distribution. install takes an explicit --host claude; there is no default\n"
        "host and no wildcard.\n"
    )


def runtime_admission() -> tuple[bool, dict[str, Any], str | None]:
    observed = ".".join(str(value) for value in sys.version_info[:3])
    isolated = bool(sys.flags.isolated) and bool(sys.flags.no_user_site) and bool(sys.dont_write_bytecode)
    admitted = observed == "3.12.11" and isolated
    runtime = {
        "interpreter": os.path.abspath(sys.executable),
        "isolated": isolated,
        "state": "admitted" if admitted else "refused",
        "version": observed,
    }
    if admitted:
        return True, runtime, None
    details: list[str] = []
    if observed != "3.12.11":
        details.append(f"expected Python 3.12.11, observed {observed}")
    if not isolated:
        details.append("expected direct -I -B execution")
    return False, runtime, "; ".join(details)


def load_guard(script_path: Path) -> ModuleType:
    path = script_path.with_name("ccodex_sdlc_readonly.py")
    if path.is_symlink() or not path.is_file():
        raise ReportInvariantError(f"read-only guard is unavailable: {path}")
    spec = importlib.util.spec_from_file_location("_ccodex_sdlc_readonly_guard", path)
    if spec is None or spec.loader is None:
        raise ReportInvariantError(f"cannot load read-only guard: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def lifecycle_module_path(verb: str) -> Path:
    return Path(__file__).with_name(f"{LIFECYCLE_MODULES[verb]}.py")


def load_lifecycle_module(verb: str, label: str | None = None) -> ModuleType:
    """Load one named per-verb lifecycle module by absolute file path.

    Same admission shape as ``load_guard`` here and ``load_sibling`` in the read-only guard: an
    exact physical sibling, never a symlink, never resolved through ambient ``sys.path``.  The
    read-only guard is deliberately NOT installed on this path, because it exists to block the very
    effects a lifecycle module owns; the reader hands off instead of borrowing that authority.

    The boundary between the two effect classes is ``exec_module``.  Everything refused before it
    ran nothing, so it is a clean refusal (exit 3).  Once foreign top-level code has executed, no
    absence of effect can be claimed, so a failure there is an admitted unknown effect (exit 4).
    """
    named = label or verb
    path = lifecycle_module_path(verb)
    if path.is_symlink() or not path.is_file():
        raise LifecycleRefusal(
            f"ccodex sdlc {named} is unavailable in this distribution: {str(path)!r} is absent"
        )
    spec = importlib.util.spec_from_file_location(f"_ccodex_sdlc_lifecycle_{verb}", path)
    if spec is None or spec.loader is None:
        raise LifecycleRefusal(f"ccodex sdlc {named} module cannot be loaded: {str(path)!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - any import-time failure leaves the effect unknown
        raise LifecycleUnknownEffect(
            f"ccodex sdlc {named} module failed while loading, so its effect is unknown: {exc!r}"
        ) from exc
    return module


def dispatch_lifecycle(verb: str, forwarded: list[str], *, label: str | None = None) -> int:
    """Refuse, or hand one admitted mutating vector to its per-verb module. Never mutate here.

    ``forwarded`` is the exact argv the module receives, and ``label`` is how the vector is NAMED in
    a refusal -- ``recover --apply`` rather than the bare verb, because ``recover`` alone is also a
    reader form and a refusal that named it would describe the wrong invocation.

    ``SystemExit`` from the module is deliberately NOT caught: that status is the module's own
    decision about its own effect, and re-classifying it here would overwrite the only authority
    that observed the effect.
    """
    named = label or verb
    try:
        admitted, _runtime, reason = runtime_admission()
        if not admitted:
            raise LifecycleRefusal(
                f"ccodex sdlc {named} requires its bound isolated Python 3.12.11: {reason or 'runtime admission refused'}"
            )
        module = load_lifecycle_module(verb, named)
    except LifecycleRefusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except LifecycleUnknownEffect as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    entry = getattr(module, "main", None)
    if not callable(entry):
        print(
            f"error: ccodex sdlc {named} module exposes no callable main(argv), and its top-level code"
            f" already ran, so its effect is unknown: {str(lifecycle_module_path(verb))!r}",
            file=sys.stderr,
        )
        return 4
    try:
        result = entry(list(forwarded))
    except Exception as exc:  # noqa: BLE001 - the module was entered; the effect is unknown
        print(
            f"error: ccodex sdlc {named} failed inside its module, so its effect is unknown: {exc!r}",
            file=sys.stderr,
        )
        return 4
    if isinstance(result, bool) or not isinstance(result, int) or not 0 <= result <= 4:
        print(
            f"error: ccodex sdlc {named} returned no admitted exit class ({result!r}),"
            " so its effect is unknown",
            file=sys.stderr,
        )
        return 4
    return result


def empty_projection() -> dict[str, Any]:
    return {"entries": [], "findings": [], "recovery": [], "state": "absent", "state_paths": []}


def sorted_projection(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "entries": sorted(projection["entries"], key=lambda item: (item["path"], item["name"])),
        "findings": sorted(
            projection["findings"], key=lambda item: (item["component"], item["path"], item["code"], item["message"])
        ),
        "recovery": sorted(projection["recovery"], key=lambda item: (item["component"], item["path"], item["action"])),
        "state": projection["state"],
        "state_paths": sorted(projection["state_paths"]),
    }


def escape_display(value: str) -> str:
    """Escape every control character before an artifact-derived value reaches a rendered line.

    The human render writes finding messages straight to a terminal, so a bare newline in a
    filename or in a validator reason forges a line of this command's own output, a ``\\r``
    overwrites the line already printed, and an ``\\x1b[2J`` clears the reader's screen.  The
    STORED value is never touched: this is a rendering rule.  It is re-expressed here rather than
    imported because the receipt validator is an OPTIONAL sibling and a rendering rule may not
    depend on a file that can be absent; the test module proves the two agree character for
    character.
    """
    out: list[str] = []
    for char in value:
        if char in _DISPLAY_ESCAPES:
            out.append(_DISPLAY_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\x{ord(char):02x}")
        else:
            out.append(char)
    return "".join(out)


def bounded_message(text: str) -> str:
    """One escaped, length-bounded, never-empty finding message."""
    escaped = escape_display(text) or "no reason was stated"
    if len(escaped) <= MAX_FINDING_MESSAGE_CHARS:
        return escaped
    return escaped[:MAX_FINDING_MESSAGE_CHARS] + " (truncated)"


def plane_locator(prefix: str, name: str) -> str:
    """One opaque, deterministic locator for a document whose NAME is not this reader's to echo.

    A plane directory can hold a file whose name is caller-chosen text, and the ownership
    projections already render opaque locators for exactly that reason.  A well-formed receipt is
    named ``<64 lowercase hex>.json``, which carries no operator content, so that name is kept;
    anything else is named by a digest of itself, which stays stable across runs and distinguishes
    two unrecognised neighbours without republishing either name.
    """
    stem = name[:-5] if name.endswith(".json") else ""
    if len(stem) == 64 and all(character in _HEX_CHARACTERS for character in stem):
        return f"{prefix}://{stem}"
    digest = hashlib.sha256(name.encode("utf-8", "surrogatepass")).hexdigest()
    return f"{prefix}://unrecognised-{digest[:16]}"


def safe_version(value: object) -> str | None:
    """Admit a version only in the shape the receipt family admits, so no free text is echoed."""
    if not isinstance(value, str) or not value or len(value) > MAX_VERSION_CHARS:
        return None
    if any(character not in _VERSION_CHARACTERS for character in value):
        return None
    if value[0] in ".+-" or value[-1] in ".+-":
        return None
    return value


def safe_receipt_id(value: object) -> str | None:
    """Admit a receipt id only in the family's own bounded token shape, or state nothing.

    This value is CORRELATED -- the pointer's id against each filed receipt's, and an update's
    ``supersedes`` ancestor against the receipt it names -- so an inadmissible spelling becomes
    ``None`` and correlates with nothing rather than becoming a key that silently matches the wrong
    document.  It is never rendered into a finding: it identifies a document, and the finding names
    that document by its opaque locator instead.
    """
    if not isinstance(value, str) or not value or len(value) > MAX_RECEIPT_ID_CHARS:
        return None
    if any(character not in _RECEIPT_ID_CHARACTERS for character in value):
        return None
    if value[0] == "-" or value[-1] == "-":
        return None
    return value


def strict_plane_json(text: str) -> dict[str, Any]:
    """Parse one plane document with the duplicate-key and BOTH non-finite guards applied.

    ``parse_constant`` never sees ``1e400``: the decoder turns it into ``inf`` by itself, so the
    parsed value is walked as well.  A repeated key is refused rather than resolved to whichever
    copy came last, because a document with two meanings has no observation in it.
    """
    document = strict_json_document(text.encode("utf-8"), Path("plane document"))
    _check_finite(document)
    return document


def read_plane_document(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read one plane document read-only, or NAME why it could not be read. Never follows a link.

    ``lstat`` before the open is load-bearing twice: a symlink is a redirected state surface this
    reader reports instead of following, and opening a FIFO would block until a writer that may
    never arrive.  The size is bounded before and after the read, so a file that grows between the
    two is named rather than read.
    """
    try:
        item = path.lstat()
    except OSError as exc:
        return None, f"cannot be read ({exc.strerror or exc.__class__.__name__})"
    if stat.S_ISLNK(item.st_mode):
        return None, PLANE_SYMLINK_REASON
    if not stat.S_ISREG(item.st_mode):
        return None, "is not a regular file"
    if item.st_size > MAX_PLANE_DOCUMENT_BYTES:
        return None, f"is larger than the {MAX_PLANE_DOCUMENT_BYTES}-byte ceiling"
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_PLANE_DOCUMENT_BYTES + 1)
    except OSError as exc:
        return None, f"cannot be read ({exc.strerror or exc.__class__.__name__})"
    if len(raw) > MAX_PLANE_DOCUMENT_BYTES:
        return None, f"grew past the {MAX_PLANE_DOCUMENT_BYTES}-byte ceiling while being read"
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return None, "is not UTF-8 text"
    try:
        return strict_plane_json(text), None
    except Exception as exc:  # noqa: BLE001 - any parse outcome is one classification, never a raise
        return None, f"is not one strict JSON object ({exc})"


def list_plane_documents(directory: Path) -> tuple[list[str], str | None]:
    """List one plane directory's candidate document names, bounded and sorted, or name the absence.

    ``absent`` is a state, not a failure: a distribution that was never activated has no plane, and
    that reads as absent with a reason rather than as a defect this reader invented.
    """
    try:
        item = directory.lstat()
    except FileNotFoundError:
        return [], "absent"
    except OSError as exc:
        return [], f"cannot be listed ({exc.strerror or exc.__class__.__name__})"
    if stat.S_ISLNK(item.st_mode):
        return [], PLANE_SYMLINK_REASON
    if not stat.S_ISDIR(item.st_mode):
        return [], "is not a directory"
    try:
        names = sorted(entry.name for entry in os.scandir(directory))
    except OSError as exc:
        return [], f"cannot be listed ({exc.strerror or exc.__class__.__name__})"
    documents = [name for name in names if name.endswith(".json")]
    if len(documents) > MAX_PLANE_DOCUMENTS:
        return documents[:MAX_PLANE_DOCUMENTS], PLANE_OVERFULL_REASON
    return documents, None


def load_activation_validator(
    script_path: Path, guard: ModuleType
) -> tuple[ModuleType | None, str | None]:
    """Load the receipt family's own seal validator, or name why the seal cannot be assessed.

    The validator is an optional sibling: a distribution that ships this reader without it is not
    broken, it simply cannot state seal validity, and an unassessable seal is recorded as unknown
    with a reason rather than assumed valid OR reported as invalid.  A drifted closed vocabulary
    declines the same way, because a matrix this reader guessed would read as an observation.
    """
    path = script_path.with_name(f"{ACTIVATION_VALIDATOR_MODULE}.py")
    if path.is_symlink() or not path.is_file():
        return None, "the distribution-activation seal validator is absent from this distribution"
    try:
        module = guard.load_sibling(script_path, ACTIVATION_VALIDATOR_MODULE)
    except Exception as exc:  # noqa: BLE001 - an unloadable validator is unknown, never a raise
        return None, f"the distribution-activation seal validator could not be loaded ({exc})"
    for name in ("derive", "VERDICT_VALIDATED", "RECEIPT_KIND", *EXPECTED_RECEIPT_VOCABULARIES):
        if not hasattr(module, name):
            return None, f"the distribution-activation seal validator exposes no {name}"
    if getattr(module, "RECEIPT_KIND", None) != EXPECTED_RECEIPT_KIND:
        return None, "the distribution-activation seal validator names another receipt kind"
    for name, expected in EXPECTED_RECEIPT_VOCABULARIES.items():
        if tuple(getattr(module, name)) != expected:
            return None, f"the distribution-activation seal validator's {name} vocabulary drifted"
    if not callable(module.derive):
        return None, "the distribution-activation seal validator exposes no callable derive"
    return module, None


def receipt_observation(
    locator: str, *, state: str, seal_valid: bool | None, reason: str | None
) -> dict[str, Any]:
    """One receipt observation with every field present and nothing yet read out of the document.

    Shared by the assessed and the unassessable paths so a field added to one is never missing from
    the other, and so no consumer has to tell an absent key from a null one.
    """
    return {
        "locator": locator,
        "seal_valid": seal_valid,
        "state": state,
        "reason": reason,
        "activated_version": None,
        "requested_version": None,
        "version_source": None,
        "operation": None,
        "terminal_phase": None,
        "effect_state": None,
        "archive_sha256": None,
        "candidate_id": None,
        "unknown_subjects": [],
        "interrupted": False,
        # The identity this receipt claims, and the identities it claims to replace. Both are read
        # only out of a VALIDATED document, and both stay `None`/empty otherwise: an unvalidated
        # document's ancestors are unchecked text, and letting one of them retire a neighbour would
        # hand any writable file the power to hide a real activation from this reader.
        "receipt_id": None,
        "supersedes": [],
        # Whether another receipt on this plane says it replaced this one, and whether this receipt
        # is the plane's CURRENT statement. Both default to the honest negative.
        "superseded": False,
        "active": False,
    }


def observe_activation_receipt(
    document: dict[str, Any], validator: ModuleType, locator: str
) -> dict[str, Any]:
    """Assess ONE distribution-activation receipt through the family's own validator.

    The subject handed to ``derive`` is the opaque locator, so no absolute path can reach a reason
    line.  Nothing is read out of a receipt that did not validate: an unvalidated document's fields
    are unchecked text, and echoing them would publish exactly what the seal exists to bound.
    """
    observation = receipt_observation(locator, state="invalid", seal_valid=False, reason=None)
    try:
        result = validator.derive("validate", document, locator)
    except Exception as exc:  # noqa: BLE001 - a validator that cannot assess is unknown, not a crash
        observation["state"] = "unassessed"
        observation["reason"] = f"the seal validator could not assess this receipt ({exc})"
        return observation
    if not isinstance(result, dict) or result.get("verdict") != validator.VERDICT_VALIDATED:
        reasons = [reason for reason in (result or {}).get("reasons", []) if isinstance(reason, str)]
        observation["reason"] = reasons[0] if reasons else "the seal validator stated no reason"
        return observation
    body = document.get("body")
    if not isinstance(body, dict):
        observation["state"] = "unassessed"
        observation["reason"] = "the validated receipt carries no body object"
        return observation
    unknowns = body.get("unknowns")
    subjects = sorted(
        {
            entry["subject"]
            for entry in (unknowns if isinstance(unknowns, list) else [])
            if isinstance(entry, dict) and isinstance(entry.get("subject"), str)
        }
    )
    version_source = body.get("version_source")
    resolved = safe_version(body.get("resolved_version"))
    # Built into a LOCAL before the literal that reports it: a comprehension inside a dict literal is
    # evaluated after its sibling keys, and this project has already lost a whole list that way.
    ancestors = document.get("ancestors")
    superseded_ids: list[str] = []
    for reference in ancestors if isinstance(ancestors, list) else []:
        if not isinstance(reference, dict):
            continue
        # `derived-from` names the ACQUISITION this receipt drew its payload from, and only
        # `supersedes` names an activation receipt this one replaced. The kind is checked too,
        # because a reference to another family's document never retires a receipt on this plane.
        if reference.get("relation") != SUPERSEDES_RELATION:
            continue
        if reference.get("expected_kind") != EXPECTED_RECEIPT_KIND:
            continue
        named = safe_receipt_id(reference.get("receipt_id"))
        if named is not None and named not in superseded_ids:
            superseded_ids.append(named)
    superseded_ids.sort()
    observation.update(
        {
            "seal_valid": True,
            "state": "validated",
            "receipt_id": safe_receipt_id(document.get("receipt_id")),
            "supersedes": superseded_ids,
            "operation": body.get("operation") if isinstance(body.get("operation"), str) else None,
            "terminal_phase": body.get("terminal_phase") if isinstance(body.get("terminal_phase"), str) else None,
            "effect_state": body.get("effect_state") if isinstance(body.get("effect_state"), str) else None,
            "version_source": version_source if isinstance(version_source, str) else None,
            "requested_version": safe_version(body.get("requested_version")),
            # A resolved version counts as ACTIVATED only from a source that read it back. The
            # requested value is what the caller asked for and never becomes readback.
            "activated_version": resolved if version_source in PROVEN_VERSION_SOURCES else None,
            "archive_sha256": body.get("archive_sha256") if isinstance(body.get("archive_sha256"), str) else None,
            "candidate_id": body.get("candidate_id") if isinstance(body.get("candidate_id"), str) else None,
            "unknown_subjects": subjects,
        }
    )
    observation["interrupted"] = (
        observation["effect_state"] in INTERRUPTED_EFFECT_STATES
        or observation["terminal_phase"] in INTERRUPTED_TERMINAL_PHASES
    )
    return observation


def observe_selected_payload(
    directory: Path,
    read_document: Any = read_plane_document,
) -> dict[str, Any]:
    """Observe the acquired candidates the acquisition plane recorded: the selectable payloads.

    The acquisition receipt is SEALED and is never mutated, opened for writing, or re-derived here
    (agentic-sdlc-0cce); it is read for the identity it already states.  It carries no version, so
    the payload version comes from the candidate root's own manifest and is unknown-with-a-reason
    whenever that manifest cannot be read.

    DISCLOSURE (agentic-sdlc-7c7d): the candidate manifest read this drives, in
    ``observe_candidate_version``, ``lstat``-guards the manifest FILE the same way
    ``read_plane_document`` guards every other plane document -- a symlinked leaf is reported, never
    opened -- but the candidate root itself came from a sealed receipt's recorded path, and neither
    that root nor any directory above it is re-checked for a link planted since the receipt sealed.
    This is hardening-only, not a live gap this reader's own output can carry: the one value read
    through it, `payload_version`, passes through `safe_version`'s closed 64-character charset before
    it reaches a finding or a report, so a redirected read can change which plausible-looking version
    string appears here and nothing else -- it can name no path, inject no control character, and
    forge no line.
    """
    names, listing_reason = list_plane_documents(directory)
    payloads: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []
    for name in names:
        locator = plane_locator("acquisition-receipt", name)
        document, reason = read_document(directory / name)
        if document is None:
            unreadable.append({"locator": locator, "reason": reason or "cannot be read"})
            continue
        if document.get("schema_version") != ACQUISITION_RECEIPT_SCHEMA:
            unreadable.append(
                {"locator": locator, "reason": f"is not one {ACQUISITION_RECEIPT_SCHEMA} document"}
            )
            continue
        archive = document.get("archive_sha256")
        root_value = document.get("candidate_root_absolute_physical_path")
        version, version_reason = (None, "the receipt states no candidate root")
        if isinstance(root_value, str) and root_value:
            version, version_reason = observe_candidate_version(Path(root_value), read_document)
        payloads.append(
            {
                "locator": locator,
                "archive_sha256": archive if isinstance(archive, str) else None,
                "terminal_phase": document.get("terminal_phase")
                if isinstance(document.get("terminal_phase"), str)
                else None,
                "selection": document.get("selection") if isinstance(document.get("selection"), str) else None,
                "acquired": document.get("terminal_phase") == ACQUISITION_TERMINAL_PHASE
                and document.get("selection") == ACQUISITION_SELECTION,
                "payload_version": version,
                "payload_version_reason": version_reason,
            }
        )
    state = "absent" if not payloads and not unreadable else "observed"
    return {
        "state": state,
        "listing_reason": listing_reason,
        "payloads": payloads,
        "unreadable": unreadable,
        "versions": sorted({payload["payload_version"] for payload in payloads if payload["payload_version"]}),
    }


def observe_candidate_version(
    candidate_root: Path, read_document: Any = read_plane_document
) -> tuple[str | None, str | None]:
    """Read one acquired candidate's own product version out of its manifest, or name the absence."""
    document, reason = read_document(candidate_root / "manifest.json")
    if document is None:
        return None, f"the candidate manifest {reason or 'cannot be read'}"
    version = safe_version(document.get("product_version"))
    if version is None:
        return None, "the candidate manifest states no admissible product_version"
    return version, None


def observe_active_pointer(
    location: Path | None | _Unsupplied,
    directory: Path,
    validator: ModuleType | None,
    validator_reason: str | None,
    read_document: Any = read_plane_document,
) -> dict[str, Any]:
    """Observe the plane's ONE active statement, or NAME why it states nothing this reader can use.

    ``activation/active-receipt.json`` sits beside the receipts directory, so an unsupplied location
    is derived from that layout rather than from an environment this reader would have to re-resolve.
    A caller that names ``None`` has said "treat this plane as having no pointer", which is a
    different input from naming nothing at all, and the two are recorded as different states.

    Absent is a STATE, not a failure: a plane activated before the pointer existed, and a plane that
    was never activated, both have no pointer, and neither is a defect this reader invented.  Every
    other outcome is named -- a symlink is reported instead of followed, an unparsable document is
    named, and a document whose seal does not validate has nothing read out of it -- and in every one
    of those cases the pointer disambiguates nothing, so the plane falls back to what the receipts
    themselves say about each other.
    """
    observation: dict[str, Any] = {
        "state": "absent",
        "reason": None,
        "receipt_id": None,
        "correlation": "not-correlated",
        # Whether a caller named this location at all. `UNSUPPLIED` means the layout's own convention
        # was used, and that is a different input from a caller that named one.
        "location_supplied": not isinstance(location, _Unsupplied),
    }
    if location is None:
        observation["state"] = "unnamed"
        observation["reason"] = "no active-receipt pointer location was supplied"
        return observation
    path = directory.parent / ACTIVE_POINTER_NAME if isinstance(location, _Unsupplied) else location
    try:
        item = path.lstat()
    except FileNotFoundError:
        observation["reason"] = "absent"
        return observation
    except OSError as exc:
        observation["state"] = "unreadable"
        observation["reason"] = f"cannot be read ({exc.strerror or exc.__class__.__name__})"
        return observation
    if stat.S_ISLNK(item.st_mode):
        observation["state"] = "unreadable"
        observation["reason"] = PLANE_SYMLINK_REASON
        return observation
    document, reason = read_document(path)
    if document is None:
        observation["state"] = "unreadable"
        observation["reason"] = reason or "cannot be read"
        return observation
    if validator is None:
        observation["state"] = "unassessed"
        observation["reason"] = validator_reason or "the seal cannot be assessed"
        return observation
    assessed = observe_activation_receipt(document, validator, ACTIVE_POINTER_LOCATOR)
    if assessed["state"] != "validated":
        observation["state"] = assessed["state"]
        observation["reason"] = assessed["reason"]
        return observation
    observation["state"] = "observed"
    observation["receipt_id"] = assessed["receipt_id"]
    if assessed["receipt_id"] is None:
        observation["reason"] = "states no admissible receipt id, so it correlates with no receipt"
    return observation


def observe_activation(
    directory: Path,
    validator: ModuleType | None,
    validator_reason: str | None,
    read_document: Any = read_plane_document,
    *,
    active_pointer: Path | None | _Unsupplied = UNSUPPLIED,
) -> dict[str, Any]:
    """Observe the distribution-activation plane: presence, seal validity, versions, transitions."""
    names, listing_reason = list_plane_documents(directory)
    receipts: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []
    for name in names:
        locator = plane_locator("activation-receipt", name)
        document, reason = read_document(directory / name)
        if document is None:
            unreadable.append({"locator": locator, "reason": reason or "cannot be read"})
            continue
        if validator is None:
            receipts.append(
                receipt_observation(
                    locator,
                    state="unassessed",
                    seal_valid=None,
                    reason=validator_reason or "the seal cannot be assessed",
                )
            )
            continue
        receipts.append(observe_activation_receipt(document, validator, locator))
    validated = [receipt for receipt in receipts if receipt["state"] == "validated"]
    activated = [
        receipt for receipt in validated if receipt["terminal_phase"] in ACTIVE_TERMINAL_PHASES
    ]
    pointer = observe_active_pointer(active_pointer, directory, validator, validator_reason, read_document)
    # WHICH FILED RECEIPTS ARE STILL THIS PLANE'S STATEMENT. An update retains the receipt it
    # replaced, so a plane with a history holds more than one activation receipt by design. A receipt
    # another VALIDATED receipt names in a `supersedes` ancestor has been replaced, and the pointer --
    # when it is readable, sealed, and correlates with exactly one filed receipt -- is the plane's own
    # statement of which receipt is current and takes precedence over the ancestor walk.
    replaced: set[str] = set()
    for receipt in validated:
        replaced.update(receipt["supersedes"])
    for receipt in receipts:
        receipt["superseded"] = receipt["receipt_id"] is not None and receipt["receipt_id"] in replaced
    current = None
    if pointer["state"] == "observed" and pointer["receipt_id"] is not None:
        named = [receipt for receipt in activated if receipt["receipt_id"] == pointer["receipt_id"]]
        if len(named) == 1:
            current = named[0]
            pointer["correlation"] = "matched"
        elif not named:
            pointer["correlation"] = "names-no-filed-activation"
        else:
            # Two documents claiming one identity is an ambiguity this reader reports rather than
            # resolves by picking one, which is the same posture the update verb takes on retention.
            pointer["correlation"] = "names-more-than-one-filed-document"
    effective = [current] if current is not None else [
        receipt for receipt in activated if not receipt["superseded"]
    ]
    # `active` and `superseded` are independent facts and BOTH can hold at once: an update that filed
    # its receipt and was killed before replacing the pointer leaves a sealed receipt whose ancestor
    # names the receipt this plane still points at. The pointer is the plane's OWN statement of what
    # it owns, so it wins; the other document's claim stays visible in `superseded_activations`
    # instead of being resolved into a version this plane never activated.
    for receipt in effective:
        receipt["active"] = True
    versions = sorted({receipt["activated_version"] for receipt in effective if receipt["activated_version"]})
    # Both lists are built into locals BEFORE the literal that reports them, because a comprehension
    # inside a dict literal is evaluated after its sibling keys.
    superseded_locators = [receipt["locator"] for receipt in receipts if receipt["superseded"]]
    active_locators = [receipt["locator"] for receipt in effective]
    unversioned = [receipt["locator"] for receipt in effective if not receipt["activated_version"]]
    if not receipts and not unreadable:
        state = "absent"
    elif unreadable or any(receipt["state"] == "invalid" for receipt in receipts):
        state = "unreadable"
    elif any(receipt["state"] != "validated" for receipt in receipts):
        # The plane is readable; its SEALS are what could not be assessed, and those are different
        # states an operator acts on differently.
        state = "unassessed"
    elif len(versions) > 1:
        state = "ambiguous"
    else:
        state = "observed"
    return {
        "state": state,
        "listing_reason": listing_reason,
        "validator_reason": validator_reason,
        "receipts": receipts,
        "unreadable": unreadable,
        "activated_versions": versions,
        # An activated receipt whose version has no proven source states no activated version, and
        # the difference between "not supplied" and "supplied unusable" is kept.
        "unversioned_activations": unversioned,
        "interrupted": [receipt["locator"] for receipt in receipts if receipt["interrupted"]],
        "active_pointer": pointer,
        # The plane's current statement and its retained history, kept as separate lists so no
        # consumer has to re-derive either one from a count.
        "active_activations": active_locators,
        "superseded_activations": superseded_locators,
    }


def reconcile_activation(activation: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    """Correlate each activated distribution with an acquired payload, consulting recorded unknowns.

    A receipt that RECORDS an unknown about ``archive_sha256`` has already said its own payload
    identity was not observed, so this reader may not then treat that digest as a fact: the
    correlation is unknown, not matched and not unmatched.
    """
    acquired = {
        payload["archive_sha256"]
        for payload in selection["payloads"]
        if payload["acquired"] and payload["archive_sha256"]
    }
    unknown: list[str] = []
    unmatched: list[str] = []
    matched: list[str] = []
    for receipt in activation["receipts"]:
        if receipt["state"] != "validated" or receipt["terminal_phase"] not in ACTIVE_TERMINAL_PHASES:
            continue
        if "archive_sha256" in receipt["unknown_subjects"] or not receipt["archive_sha256"]:
            unknown.append(receipt["locator"])
        elif receipt["archive_sha256"] in acquired:
            matched.append(receipt["locator"])
        else:
            unmatched.append(receipt["locator"])
    selected = selection["versions"]
    activated = activation["activated_versions"]
    if not activated or not selected:
        delta = "unknown"
    elif set(activated) == set(selected):
        delta = "same"
    else:
        delta = "different"
    return {
        "matched": sorted(matched),
        "unknown": sorted(unknown),
        "unmatched": sorted(unmatched),
        "selected_versions": selected,
        "activated_versions": activated,
        "version_delta": delta,
    }


def observe_host_compatibility(
    contract: dict[str, Any], observed_host_version: str | None = None
) -> dict[str, Any]:
    """Compare the contract's DECLARED incompatibilities against the observed host.

    No version arithmetic happens here.  ``minimum_host_version`` is declared eligibility-only, and
    ordering two version strings requires a scheme this reader would have to invent, so the only
    verdict taken is exact membership in the declared-incompatible list.  The host version itself is
    not observable by a read-only command -- it requires executing the host -- so it is unknown with
    that reason unless a caller supplies an already-observed value.
    """
    compatibility = contract.get("compatibility")
    core = compatibility.get("core") if isinstance(compatibility, dict) else None
    declared = compatibility.get("known_incompatible_host_versions") if isinstance(compatibility, dict) else None
    if not isinstance(core, dict) or not isinstance(declared, list):
        return {
            "state": "unknown",
            "host": None,
            "minimum_host_version": None,
            "observed_host_version": None,
            "reason": "the release contract declares no compatibility surface",
            "declared_incompatible": [],
        }
    incompatible = sorted({value for value in declared if isinstance(value, str) and value})
    supplied = safe_version(observed_host_version)
    if observed_host_version is None:
        state, reason = "unknown", (
            "the host version is not observable by a read-only command: reading it means executing "
            "the host, which this reader never does"
        )
    elif supplied is None:
        state, reason = "unknown", "the supplied host version is not an admissible version string"
    elif supplied in incompatible:
        state, reason = "declared-incompatible", (
            f"the release contract declares host version {supplied} incompatible"
        )
    else:
        state, reason = "not-declared-incompatible", (
            "the observed host version is not on the declared-incompatible list; the declared "
            "minimum is eligibility only and is not decided here"
        )
    return {
        "state": state,
        "host": core.get("host") if isinstance(core.get("host"), str) else None,
        "minimum_host_version": safe_version(core.get("minimum_host_version")),
        "observed_host_version": supplied,
        "reason": reason,
        "declared_incompatible": incompatible,
    }


def observe_readiness(
    contract: dict[str, Any],
    *,
    acquisition_receipts: Path,
    activation_receipts: Path,
    validator: ModuleType | None,
    validator_reason: str | None,
    observed_host_version: str | None = None,
    read_document: Any = read_plane_document,
    active_pointer: Path | None | _Unsupplied = UNSUPPLIED,
) -> dict[str, Any]:
    """One read-only host-level readiness observation. Every location above is a parameter."""
    selection = observe_selected_payload(acquisition_receipts, read_document)
    activation = observe_activation(
        activation_receipts,
        validator,
        validator_reason,
        read_document,
        active_pointer=active_pointer,
    )
    return {
        "activation": activation,
        "compatibility": observe_host_compatibility(contract, observed_host_version),
        "reconciliation": reconcile_activation(activation, selection),
        "selection": selection,
    }


def reason_code(reason: str) -> str:
    """Map one named read failure onto the report's closed code set by exact reason identity."""
    if reason == PLANE_SYMLINK_REASON:
        return "state-symlinked"
    if reason == PLANE_OVERFULL_REASON:
        return "state-ambiguous"
    return "state-unreadable"


def readiness_finding(code: str, message: str, locator: str) -> dict[str, str]:
    return {"code": code, "component": "checkout", "message": bounded_message(message), "path": locator}


def readiness_findings(readiness: dict[str, Any]) -> list[dict[str, str]]:
    """Project the readiness observation onto the report's CLOSED finding vocabulary.

    Only a state the v1 vocabulary can name honestly becomes a finding.  An absent plane, an
    unknown host version, and an activated version that differs from the selected payload are
    dimension VALUES, not defects, and this reader does not borrow a defect code to state one: the
    report policy carries no `distribution` dimension and no code for a version delta, and widening
    a byte-pinned policy is not this surface's authority.

    DISCLOSURE (agentic-sdlc-7c7d): these findings render verb-uniformly -- `inspect`, `status`,
    `doctor`, and `recover --dry-run` all call this same function and see the same list, including
    `inspect`, by the pre-existing design the call site documents (every reader verb renders ONE
    semantic report, so a finding one verb hid would make another verb's identical-looking report a
    differently-shaped truth about the same host).  That is a decision already made, not a gap.  A
    FUTURE distribution dimension -- one that, unlike the values above, needs to say something only
    some verbs should show -- must decide per-verb rendering explicitly in its own policy seed rather
    than assume this function's uniform call site will do it silently.
    """
    findings: list[dict[str, str]] = []
    activation = readiness["activation"]
    selection = readiness["selection"]
    for prefix, plane in (("activation-plane", activation), ("acquisition-plane", selection)):
        reason = plane["listing_reason"]
        if reason is not None and reason != "absent":
            findings.append(
                readiness_finding(
                    reason_code(reason),
                    f"the {prefix.replace('-', ' ')} directory {reason}",
                    f"{prefix}://receipts",
                )
            )
        for item in plane["unreadable"]:
            findings.append(
                readiness_finding(
                    reason_code(item["reason"]),
                    f"a recorded {prefix.split('-')[0]} document {item['reason']}",
                    item["locator"],
                )
            )
    for receipt in activation["receipts"]:
        if receipt["state"] == "invalid":
            findings.append(
                readiness_finding(
                    "state-malformed",
                    "the recorded distribution-activation receipt did not validate: "
                    f"{receipt['reason']}",
                    receipt["locator"],
                )
            )
        elif receipt["state"] == "unassessed":
            findings.append(
                readiness_finding(
                    "state-ambiguous",
                    f"the recorded distribution-activation receipt was not assessed: {receipt['reason']}",
                    receipt["locator"],
                )
            )
        if receipt["interrupted"]:
            findings.append(
                readiness_finding(
                    "pending-recovery",
                    "the recorded distribution-activation transition did not complete "
                    f"(effect {receipt['effect_state']}, phase {receipt['terminal_phase']})",
                    receipt["locator"],
                )
            )
    pointer = activation["active_pointer"]
    if pointer["state"] == "unreadable":
        findings.append(
            readiness_finding(
                reason_code(pointer["reason"] or ""),
                f"the activation plane's active-receipt pointer {pointer['reason']}",
                ACTIVE_POINTER_LOCATOR,
            )
        )
    elif pointer["state"] == "invalid":
        findings.append(
            readiness_finding(
                "state-malformed",
                f"the activation plane's active-receipt pointer did not validate: {pointer['reason']}",
                ACTIVE_POINTER_LOCATOR,
            )
        )
    elif pointer["correlation"] == "names-no-filed-activation":
        findings.append(
            readiness_finding(
                "state-ambiguous",
                "the activation plane's active-receipt pointer names no validated activation receipt "
                "filed on this plane, so what this plane owns cannot be determined here",
                ACTIVE_POINTER_LOCATOR,
            )
        )
    elif pointer["correlation"] == "names-more-than-one-filed-document":
        findings.append(
            readiness_finding(
                "state-ambiguous",
                "the activation plane's active-receipt pointer names a receipt identity more than "
                "one filed document claims, and this reader does not resolve which one is meant",
                ACTIVE_POINTER_LOCATOR,
            )
        )
    # Counted over the receipts that are still this plane's statement. A receipt an update SUPERSEDED
    # is retained on purpose, and the pointer names the current one, so neither the retention nor the
    # history is an ambiguity; two receipts that name each other's identity in no supersedes ancestor
    # and no pointer to choose between them still is.
    if len(activation["activated_versions"]) > 1:
        findings.append(
            readiness_finding(
                "state-ambiguous",
                "the activation plane records more than one activated version: "
                + ", ".join(activation["activated_versions"]),
                "activation-plane://receipts",
            )
        )
    for locator in activation["unversioned_activations"]:
        findings.append(
            readiness_finding(
                "state-ambiguous",
                "the recorded activation states no version from a source that read it back",
                locator,
            )
        )
    reconciliation = readiness["reconciliation"]
    for locator in reconciliation["unknown"]:
        findings.append(
            readiness_finding(
                "state-ambiguous",
                "the recorded activation names no observed payload digest, so which acquired "
                "payload is activated cannot be determined here",
                locator,
            )
        )
    for locator in reconciliation["unmatched"]:
        findings.append(
            readiness_finding(
                "state-ambiguous",
                "the activated distribution matches no acquired payload on this host, so its "
                "version cannot be corroborated here",
                locator,
            )
        )
    compatibility = readiness["compatibility"]
    if compatibility["state"] == "declared-incompatible":
        findings.append(
            readiness_finding(
                "state-unsupported",
                compatibility["reason"],
                "release-contract://compatibility/known_incompatible_host_versions",
            )
        )
    return findings


def observe_host_readiness(
    contract: dict[str, Any], adapters: tuple[ModuleType, ModuleType, ModuleType]
) -> dict[str, Any]:
    """Resolve this host's two lifecycle planes and observe them, reusing the guarded adapters.

    The planes live under the operator's own XDG state root beside the ownership documents the
    projections already read (spec Decision 11), and the acquisition layout is the one
    ``write_acquisition_receipt`` seals into.  Resolution is separated from observation so a test
    can hand ``observe_readiness`` its own directories.
    """
    guard, operator_tools, _bundle = adapters
    state_root = operator_tools.state_root_for(operator_tools.absolute(Path.home()))
    plane = state_root / STATE_PLANE_DIRECTORY
    validator, validator_reason = load_activation_validator(Path(__file__), guard)
    return observe_readiness(
        contract,
        acquisition_receipts=plane.joinpath(*ACQUISITION_PLANE),
        activation_receipts=plane.joinpath(*ACTIVATION_PLANE),
        validator=validator,
        validator_reason=validator_reason,
    )


def load_read_only_adapters() -> tuple[ModuleType, ModuleType, ModuleType]:
    """Install the process guard once and load the two ownership adapters by absolute path.

    Extracted so the ownership projections and the readiness observation share ONE guarded load:
    installing the guard twice would nest its wrappers, and loading the adapters twice would give
    two module objects whose blocked-mutator state is separately owned.
    """
    script_path = Path(__file__)
    guard = load_guard(script_path)
    guard.install()
    operator_tools = guard.load_sibling(script_path, "install_operator_tools")
    bundle = guard.load_sibling(script_path, "install_skill_bundle")
    guard.block_lifecycle_mutators(operator_tools, bundle)
    return guard, operator_tools, bundle


def recovery_configs(
    root: Path, operator_tools: ModuleType, bundle: ModuleType
) -> tuple[Any, Any, Path]:
    """Resolve the two substrate configurations and this host's activation receipts plane, once.

    ONE construction site, because the ownership projections and the recovery plan must describe the
    same selection: a plan derived against a differently-configured home would carry a digest that
    the mutating form could never re-derive.  Only ``dry_run`` differs on the mutating side, and it
    participates in no classification.
    """
    home = operator_tools.absolute(Path.home())
    state_root = operator_tools.state_root_for(home)
    bin_dir = operator_tools.default_bin_dir(home)
    operator_config = operator_tools.Config(root, home, bin_dir, state_root, True, False)
    codex_home_value = os.environ.get("CODEX_HOME")
    codex_home = Path(codex_home_value) if codex_home_value and codex_home_value.strip() else home / ".codex"
    bundle_config = bundle.Config(root, home, codex_home, "auto", True, "all", state_root)
    plane = state_root / STATE_PLANE_DIRECTORY
    return operator_config, bundle_config, plane.joinpath(*ACTIVATION_PLANE)


def observe_projections(
    root: Path, adapters: tuple[ModuleType, ModuleType, ModuleType] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    _guard, operator_tools, bundle = adapters if adapters is not None else load_read_only_adapters()

    operator_config, bundle_config, _receipts = recovery_configs(root, operator_tools, bundle)
    return (
        sorted_projection(operator_tools.readonly_projection(operator_config)),
        sorted_projection(bundle.readonly_projection(bundle_config)),
    )


def load_recovery_planner(
    script_path: Path, guard: ModuleType
) -> tuple[ModuleType | None, str | None]:
    """Load the recovery plan's own derivation, or name why no digest can be rendered.

    Same posture as ``load_activation_validator``: an OPTIONAL sibling, refused rather than searched
    for, and a distribution that ships this reader without it is not broken -- it simply cannot state
    a plan digest, which is recorded as unavailable WITH a reason rather than invented.  Deriving is
    pure observation, which is what makes it safe to call while the read-only guard is installed; the
    module's mutating entry point is never touched here.
    """
    path = script_path.with_name(f"{RECOVER_MODULE}.py")
    if path.is_symlink() or not path.is_file():
        return None, "the recovery plan derivation is absent from this distribution"
    try:
        module = guard.load_sibling(script_path, RECOVER_MODULE)
    except Exception as exc:  # noqa: BLE001 - an unloadable planner is unknown, never a raise
        return None, f"the recovery plan derivation could not be loaded ({exc})"
    for name in ("PLAN_SCHEMA", "derive_plan"):
        if not hasattr(module, name):
            return None, f"the recovery plan derivation exposes no {name}"
    if getattr(module, "PLAN_SCHEMA", None) != RECOVERY_PLAN_SCHEMA:
        return None, "the recovery plan derivation names another plan schema"
    if not callable(module.derive_plan):
        return None, "the recovery plan derivation exposes no callable derive_plan"
    return module, None


def recovery_plan_line(root: Path, adapters: tuple[ModuleType, ModuleType, ModuleType]) -> str:
    """Render the ONE line that carries the approval token of this exact assessment.

    It is written to stderr rather than into the report, and that is deliberate twice over: the v1
    report document is byte-pinned by a policy this surface has no authority to widen, and
    ``recover --dry-run`` must stay byte-for-byte the read-only assessment it already is on stdout in
    BOTH its human and its canonical JSON form.  The digest is an approval token, not report data.
    """
    guard, operator_tools, bundle = adapters
    planner, reason = load_recovery_planner(Path(__file__), guard)
    if planner is None:
        return f"recovery plan: unavailable ({bounded_message(reason or 'no reason was stated')})\n"
    try:
        operator_config, bundle_config, receipts = recovery_configs(root, operator_tools, bundle)
        plan, digest = planner.derive_plan(
            operator_tools=operator_tools,
            operator_config=operator_config,
            bundle=bundle,
            bundle_config=bundle_config,
            activation_receipts=receipts,
        )
        # The digest and items admission stay INSIDE this try, and ``plan`` is shape-checked before
        # any subscript: a schema-lying sibling that returns a non-dict ``plan`` (or one with no
        # ``items`` list) must yield this same handled error, never a traceback after the report has
        # already been emitted on stdout.
        if not isinstance(digest, str) or len(digest) != 64 or any(
            character not in _HEX_CHARACTERS for character in digest
        ):
            return "recovery plan: unavailable (the derivation returned no admissible plan digest)\n"
        if not isinstance(plan, dict) or not isinstance(plan.get("items"), list):
            return "recovery plan: unavailable (the derivation returned no admissible plan shape)\n"
        if not plan["items"]:
            return "recovery plan: nothing to recover, so no plan digest is offered\n"
    except Exception as exc:  # noqa: BLE001 - a plan that cannot be derived states no digest
        return f"recovery plan: unavailable ({bounded_message(str(exc) or repr(exc))})\n"
    return (
        f"recovery plan sha256 {digest}: approve exactly this plan with"
        f" `ccodex sdlc recover {RECOVER_APPLY_FLAG} {digest}`\n"
    )


def make_finding(code: str, component: str, message: str, path: Path) -> dict[str, str]:
    return {"code": code, "component": component, "message": message, "path": str(path)}


def overall_state(operator_tools: dict[str, Any], bundle: dict[str, Any]) -> str:
    states = {operator_tools["state"], bundle["state"]}
    if "unreadable" in states:
        return "unreadable"
    if "blocked" in states:
        return "blocked"
    if "degraded" in states:
        return "degraded"
    if states == {"absent"}:
        return "absent"
    return "healthy"


def make_report(
    policy: dict[str, Any],
    command: str,
    dry_run: bool,
    checkout: dict[str, Any],
    runtime: dict[str, Any],
    operator_tools: dict[str, Any],
    bundle: dict[str, Any],
    extra_findings: list[dict[str, str]],
    *,
    exit_class: str,
) -> dict[str, Any]:
    proposals = sorted(
        [*operator_tools["recovery"], *bundle["recovery"]],
        key=lambda item: (item["component"], item["path"], item["action"]),
    )
    recovery_state = "proposed" if command == "recover" and proposals else "pending" if proposals else "not-needed"
    findings = sorted(
        [*extra_findings, *operator_tools["findings"], *bundle["findings"]],
        key=lambda item: (item["component"], item["path"], item["code"], item["message"]),
    )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "command": {"dry_run": dry_run, "verb": command},
        "checkout": checkout,
        "runtime": runtime,
        "operator_tools": operator_tools,
        "bundle": bundle,
        "recovery": {"effect": "none", "proposals": proposals, "state": recovery_state},
        "future_dimensions": {"activation": "unsupported", "release": "not-selected", "waves": "unsupported"},
        "findings": findings,
        "overall": {
            "exit_class": exit_class,
            "state": "blocked" if runtime["state"] == "refused" else overall_state(operator_tools, bundle),
        },
    }
    validate_report(report, policy)
    return report


def _require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReportInvariantError(f"{label} must be a string list")
    return value


def _check_finite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ReportInvariantError("report contains a non-finite value")
    if isinstance(value, dict):
        for nested in value.values():
            _check_finite(nested)
    elif isinstance(value, list):
        for nested in value:
            _check_finite(nested)


def validate_report(report: dict[str, Any], policy: dict[str, Any]) -> None:
    _check_finite(report)
    fields = policy["field_vocabularies"]
    vocab = policy["vocabularies"]
    _exact_keys(report, policy["report_top_level_fields"], "report")
    if report["schema_version"] != policy["report_schema_version"]:
        raise ReportInvariantError("report schema version is invalid")
    command = _exact_keys(report["command"], fields["command"], "report.command")
    if command["verb"] not in vocab["command_verbs"] or not isinstance(command["dry_run"], bool):
        raise ReportInvariantError("report command is invalid")
    checkout = _exact_keys(report["checkout"], fields["checkout"], "report.checkout")
    expected_checkout = {**EXPECTED_CHECKOUT, "release": None}
    if checkout != expected_checkout:
        raise ReportInvariantError("report checkout identity is invalid")
    runtime = _exact_keys(report["runtime"], fields["runtime"], "report.runtime")
    if runtime["state"] not in vocab["runtime_states"] or not isinstance(runtime["isolated"], bool):
        raise ReportInvariantError("report runtime is invalid")
    if not all(isinstance(runtime[field], str) and runtime[field] for field in ("interpreter", "version")):
        raise ReportInvariantError("report runtime identity is invalid")
    for component in ("operator_tools", "bundle"):
        projection = _exact_keys(report[component], fields["bundle"], f"report.{component}")
        if projection["state"] not in vocab["component_states"]:
            raise ReportInvariantError(f"report {component} state is invalid")
        paths = _require_string_list(projection["state_paths"], f"report {component} state paths")
        if paths != sorted(set(paths)):
            raise ReportInvariantError(f"report {component} state paths are not deterministic")
        for entry in projection["entries"]:
            entry = _exact_keys(entry, fields["projection_entry"], f"report {component} entry")
            if entry["state"] not in vocab["entry_states"] or not all(
                isinstance(entry[field], str) and entry[field] for field in ("name", "path")
            ):
                raise ReportInvariantError(f"report {component} entry is invalid")
        for item in projection["recovery"]:
            validate_recovery_item(item, fields, vocab)
        for finding in projection["findings"]:
            validate_finding(finding, fields, vocab)
    recovery = _exact_keys(report["recovery"], fields["recovery"], "report.recovery")
    if recovery["effect"] not in vocab["recovery_effects"] or recovery["state"] not in vocab["recovery_states"]:
        raise ReportInvariantError("report recovery is invalid")
    for proposal in recovery["proposals"]:
        validate_recovery_item(proposal, fields, vocab)
    future = _exact_keys(report["future_dimensions"], fields["future_dimensions"], "report.future_dimensions")
    if future != {"activation": "unsupported", "release": "not-selected", "waves": "unsupported"}:
        raise ReportInvariantError("report future dimensions are invalid")
    for finding in report["findings"]:
        validate_finding(finding, fields, vocab)
    overall = _exact_keys(report["overall"], fields["overall"], "report.overall")
    if overall["exit_class"] not in vocab["exit_classes"] or overall["state"] not in vocab["overall_states"]:
        raise ReportInvariantError("report overall state is invalid")
    if overall["exit_class"] == "safe-refusal" and runtime["state"] != "refused":
        raise ReportInvariantError("safe refusal requires a refused runtime")
    if overall["exit_class"] == "ok" and runtime["state"] != "admitted":
        raise ReportInvariantError("an admitted runtime is required for an ok report")


def validate_recovery_item(item: object, fields: dict[str, Any], vocab: dict[str, Any]) -> None:
    item = _exact_keys(item, fields["recovery_item"], "report recovery proposal")
    if (
        item["action"] not in vocab["recovery_actions"]
        or item["component"] not in {"operator-tools", "bundle"}
        or item["state"] not in vocab["recovery_item_states"]
        or not isinstance(item["path"], str)
        or not item["path"]
    ):
        raise ReportInvariantError("report recovery proposal is invalid")


def validate_finding(finding: object, fields: dict[str, Any], vocab: dict[str, Any]) -> None:
    finding = _exact_keys(finding, fields["finding"], "report finding")
    if finding["code"] not in vocab["finding_codes"] or finding["component"] not in vocab["finding_components"]:
        raise ReportInvariantError("report finding vocabulary is invalid")
    if not all(isinstance(finding[field], str) and finding[field] for field in ("message", "path")):
        raise ReportInvariantError("report finding values are invalid")


def render_human(report: dict[str, Any]) -> str:
    checkout = report["checkout"]
    runtime = report["runtime"]
    lines = [
        f"ccodex sdlc {report['command']['verb']}: {report['overall']['state']}",
        f"checkout: {checkout['version']} {checkout['plane']}; public channel: {checkout['public_channel'] or 'not-selected'}; public release: not-selected; certification: {checkout['certification_claim']}",
        f"runtime: {runtime['state']} ({runtime['version']}, isolated={str(runtime['isolated']).lower()})",
        f"operator-tools: {report['operator_tools']['state']}",
        f"bundle: {report['bundle']['state']}",
        f"recovery: {report['recovery']['state']} (no effects)",
        "future dimensions: release=not-selected, activation=unsupported, waves=unsupported",
    ]
    for finding in report["findings"]:
        lines.append(
            f"finding [{finding['component']}/{finding['code']}]: {finding['message']} ({finding['path']})"
        )
    for proposal in report["recovery"]["proposals"]:
        lines.append(f"recovery proposal [{proposal['component']}]: {proposal['action']} ({proposal['path']})")
    return "\n".join(lines) + "\n"


def emit(report: dict[str, Any], json_output: bool) -> None:
    sys.stdout.write(canonical_json(report) if json_output else render_human(report))


def main(argv: list[str] | None = None) -> int:
    selected = sys.argv[1:] if argv is None else argv
    try:
        # The fourth element is the ONE argument an admitted mutating vector forwards: the install
        # host, or the plan digest `recover --apply` approves.
        command, dry_run, json_output, forwarded_value = parse_command(selected)
    except UsageError as exc:
        if str(exc) == "help":
            sys.stdout.write(usage())
            return 0
        print(f"error: {exc}\n\n{usage()}", file=sys.stderr, end="")
        return 2

    if command in LIFECYCLE_VERBS:
        # Handed off before any report policy, release contract, or projection is read: a mutating
        # verb neither renders nor depends on the read report, and refusing early keeps the refusal
        # attributable to the missing module rather than to unrelated reader state.
        return dispatch_lifecycle(
            command,
            ["--host", forwarded_value] if forwarded_value is not None else [],
            label=command,
        )
    if command == "recover" and forwarded_value is not None:
        # The one mutating recover form, handed off on the same early path and for the same reason.
        # The dry-run form never reaches here, so it still acquires no writer authority.
        return dispatch_lifecycle(
            "recover",
            [RECOVER_APPLY_FLAG, forwarded_value],
            label=f"recover {RECOVER_APPLY_FLAG}",
        )

    root = Path(__file__).parent.parent
    try:
        policy = load_policy(root)
        contract = load_release_contract(root)
        checkout = checkout_identity(contract)
        admitted, runtime, reason = runtime_admission()
        if not admitted:
            report = make_report(
                policy,
                command,
                dry_run,
                checkout,
                runtime,
                empty_projection(),
                empty_projection(),
                [make_finding("runtime-admission-refused", "runtime", reason or "runtime admission refused", Path(sys.executable))],
                exit_class="safe-refusal",
            )
            emit(report, json_output)
            return 3
        adapters = load_read_only_adapters()
        operator_tools, bundle = observe_projections(root, adapters)
        # The host-level readiness dimensions are read for every reader verb rather than for
        # `doctor` alone: the four verbs render ONE semantic report, and a verb that hid a
        # malformed activation receipt the neighbouring verb reported would make `inspect --json`
        # a differently-shaped truth about the same host.
        readiness = observe_host_readiness(contract, adapters)
        report = make_report(
            policy,
            command,
            dry_run,
            checkout,
            runtime,
            operator_tools,
            bundle,
            readiness_findings(readiness),
            exit_class="ok",
        )
        emit(report, json_output)
        if command == "recover":
            # After the assessment, never instead of it: the operator sees what the plan covers and
            # then the digest that approves exactly that plan.
            sys.stderr.write(recovery_plan_line(root, adapters))
        return 0
    except (ReportInvariantError, OSError, ValueError) as exc:
        print(f"internal report construction invariant failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
