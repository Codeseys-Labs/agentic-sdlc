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
CANDIDATE_OBSERVATION_SCHEMA_VERSION = "ccodex-sdlc-candidate-observation/v1"
CANDIDATE_OBSERVATION_FLAG = "--candidate-observation-v1"
EXPECTED_CHECKOUT = {
    "certification_claim": "none",
    "plane": "checkout-development",
    "public_channel": None,
    "release_topology_adr_status": "proposed",
    "version": "0.7.3",
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


class UsageError(ValueError):
    pass


class LifecycleRefusal(RuntimeError):
    """A mutating lifecycle verb declined BEFORE any effect could occur (exit class 3)."""


class LifecycleUnknownEffect(RuntimeError):
    """A per-verb module already executed, so no absence of effect can be claimed (exit class 4)."""


class ReportInvariantError(RuntimeError):
    pass


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise ReportInvariantError(f"cannot authenticate candidate file: {path}") from exc
    return digest.hexdigest()


def _candidate_root() -> Path:
    script = Path(__file__)
    try:
        resolved = script.resolve(strict=True)
        root = resolved.parents[1]
        if script != resolved or (root / "scripts" / "ccodex_sdlc.py").resolve(strict=True) != resolved:
            raise ReportInvariantError("candidate reader is not at its physical authenticated location")
        item = root.lstat()
    except OSError as exc:
        raise ReportInvariantError("candidate root is unavailable") from exc
    if not stat.S_ISDIR(item.st_mode) or root.is_symlink():
        raise ReportInvariantError("candidate root identity is invalid")
    return root


def _candidate_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if path.is_symlink() or not path.is_file():
        raise ReportInvariantError("candidate manifest is unavailable")
    manifest = strict_json_document(path.read_bytes(), path)
    runtime = manifest.get("runtime")
    candidate_id = manifest.get("candidate_id")
    if (
        not isinstance(candidate_id, str)
        or len(candidate_id) != 64
        or any(character not in "0123456789abcdef" for character in candidate_id)
        or not isinstance(runtime, dict)
        or not isinstance(runtime.get("sha256"), str)
    ):
        raise ReportInvariantError("candidate manifest observation is invalid")
    return manifest


def load_checkout(root: Path) -> dict[str, Any]:
    path = root / "policy" / "release-contract.v1.json"
    if path.is_symlink() or not path.is_file():
        raise ReportInvariantError(f"release contract is unavailable: {path}")
    contract = strict_json_document(path.read_bytes(), path)
    checkout = contract.get("checkout")
    if contract.get("schema_version") != "release-contract/v1" or checkout != EXPECTED_CHECKOUT:
        raise ReportInvariantError("release contract does not establish the checkout-development 0.7.3 identity")
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
        raise UsageError("ccodex sdlc recover requires exactly --dry-run, optionally followed by --json")
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
        "       ccodex sdlc install --host claude\n"
        "       ccodex sdlc update\n"
        "       ccodex sdlc uninstall\n\n"
        "inspect, status, doctor, and recover read checkout-development ownership and recovery\n"
        "evidence without installing, updating, uninstalling, following, or changing state.\n"
        "`recover` is proposal-only and requires the literal --dry-run safeguard.\n\n"
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


def candidate_runtime_observation(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    admitted, runtime, reason = runtime_admission()
    expected = root / "runtime" / "python" / "bin" / "python3.12"
    try:
        executable_matches = Path(sys.executable).resolve(strict=True) == expected.resolve(strict=True)
    except OSError:
        executable_matches = False
    if not admitted or not executable_matches:
        raise ReportInvariantError(reason or "candidate runtime executable does not match its projected root")
    manifest_runtime = manifest["runtime"]
    return {
        "interpreter": "runtime/python/bin/python3.12",
        "inventory_sha256": manifest_runtime["sha256"],
        "isolated": True,
        "state": "admitted",
        "version": "3.12.11",
    }


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
    return Path(__file__).with_name(f"{LIFECYCLE_VERBS[verb]}.py")


def load_lifecycle_module(verb: str) -> ModuleType:
    """Load one named per-verb lifecycle module by absolute file path.

    Same admission shape as ``load_guard`` here and ``load_sibling`` in the read-only guard: an
    exact physical sibling, never a symlink, never resolved through ambient ``sys.path``.  The
    read-only guard is deliberately NOT installed on this path, because it exists to block the very
    effects a lifecycle module owns; the reader hands off instead of borrowing that authority.

    The boundary between the two effect classes is ``exec_module``.  Everything refused before it
    ran nothing, so it is a clean refusal (exit 3).  Once foreign top-level code has executed, no
    absence of effect can be claimed, so a failure there is an admitted unknown effect (exit 4).
    """
    path = lifecycle_module_path(verb)
    if path.is_symlink() or not path.is_file():
        raise LifecycleRefusal(
            f"ccodex sdlc {verb} is unavailable in this distribution: {str(path)!r} is absent"
        )
    spec = importlib.util.spec_from_file_location(f"_ccodex_sdlc_lifecycle_{verb}", path)
    if spec is None or spec.loader is None:
        raise LifecycleRefusal(f"ccodex sdlc {verb} module cannot be loaded: {str(path)!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - any import-time failure leaves the effect unknown
        raise LifecycleUnknownEffect(
            f"ccodex sdlc {verb} module failed while loading, so its effect is unknown: {exc!r}"
        ) from exc
    return module


def dispatch_lifecycle(verb: str, host: str | None, candidate_mode: bool) -> int:
    """Refuse, or hand one admitted mutating vector to its per-verb module. Never mutate here.

    ``SystemExit`` from the module is deliberately NOT caught: that status is the module's own
    decision about its own effect, and re-classifying it here would overwrite the only authority
    that observed the effect.
    """
    try:
        if candidate_mode:
            # Defence in depth. The candidate dispatcher's closed allowlist refuses this vector
            # first; the reader refuses it again so a direct invocation cannot bypass that.
            raise LifecycleRefusal(
                f"candidate ccodex sdlc admits only read-only inspection; {verb} is a mutating lifecycle verb"
            )
        admitted, _runtime, reason = runtime_admission()
        if not admitted:
            raise LifecycleRefusal(
                f"ccodex sdlc {verb} requires its bound isolated Python 3.12.11: {reason or 'runtime admission refused'}"
            )
        module = load_lifecycle_module(verb)
    except LifecycleRefusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except LifecycleUnknownEffect as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    entry = getattr(module, "main", None)
    if not callable(entry):
        print(
            f"error: ccodex sdlc {verb} module exposes no callable main(argv), and its top-level code"
            f" already ran, so its effect is unknown: {str(lifecycle_module_path(verb))!r}",
            file=sys.stderr,
        )
        return 4
    forwarded = ["--host", host] if host is not None else []
    try:
        result = entry(forwarded)
    except Exception as exc:  # noqa: BLE001 - the module was entered; the effect is unknown
        print(
            f"error: ccodex sdlc {verb} failed inside its module, so its effect is unknown: {exc!r}",
            file=sys.stderr,
        )
        return 4
    if isinstance(result, bool) or not isinstance(result, int) or not 0 <= result <= 4:
        print(
            f"error: ccodex sdlc {verb} returned no admitted exit class ({result!r}),"
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


def observe_projections(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    script_path = Path(__file__)
    guard = load_guard(script_path)
    guard.install()
    operator_tools = guard.load_sibling(script_path, "install_operator_tools")
    bundle = guard.load_sibling(script_path, "install_skill_bundle")
    guard.block_lifecycle_mutators(operator_tools, bundle)

    home = operator_tools.absolute(Path.home())
    state_root = operator_tools.state_root_for(home)
    bin_dir = operator_tools.default_bin_dir(home)
    operator_config = operator_tools.Config(root, home, bin_dir, state_root, True, False)
    codex_home_value = os.environ.get("CODEX_HOME")
    codex_home = Path(codex_home_value) if codex_home_value and codex_home_value.strip() else home / ".codex"
    bundle_config = bundle.Config(root, home, codex_home, "auto", True, "all", state_root)
    return (
        sorted_projection(operator_tools.readonly_projection(operator_config)),
        sorted_projection(bundle.readonly_projection(bundle_config)),
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


def make_candidate_observation(
    root: Path,
    manifest: dict[str, Any],
    command: str,
    dry_run: bool,
    runtime: dict[str, Any],
    operator_tools: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    proposals = sorted(
        [*operator_tools["recovery"], *bundle["recovery"]],
        key=lambda item: (item["component"], item["path"], item["action"]),
    )
    recovery_state = "proposed" if command == "recover" and proposals else "pending" if proposals else "not-needed"
    findings = sorted(
        [*operator_tools["findings"], *bundle["findings"]],
        key=lambda item: (item["component"], item["path"], item["code"], item["message"]),
    )
    root_item = root.lstat()
    return {
        "schema_version": CANDIDATE_OBSERVATION_SCHEMA_VERSION,
        "authority": "unadmitted-subordinate",
        "command": {"dry_run": dry_run, "verb": command},
        "identity": {
            "candidate_id": manifest["candidate_id"],
            "dispatcher_sha256": _sha256_file(root / "bin" / "ccodex"),
            "parent_process_id": os.getppid(),
            "process_id": os.getpid(),
            "root_device": root_item.st_dev,
            "root_inode": root_item.st_ino,
        },
        "runtime": runtime,
        "operator_tools": operator_tools,
        "bundle": bundle,
        "recovery": {"effect": "none", "proposals": proposals, "state": recovery_state},
        "future_dimensions": {"activation": "unsupported", "release": "unpublished", "waves": "unsupported"},
        "findings": findings,
        "overall": {"exit_class": "ok", "state": overall_state(operator_tools, bundle)},
    }


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
    candidate_mode = bool(selected and selected[0] == CANDIDATE_OBSERVATION_FLAG)
    if candidate_mode:
        selected = selected[1:]
    try:
        command, dry_run, json_output, host = parse_command(selected)
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
        return dispatch_lifecycle(command, host, candidate_mode)

    root = Path(__file__).parent.parent
    try:
        if candidate_mode:
            root = _candidate_root()
            manifest = _candidate_manifest(root)
            runtime = candidate_runtime_observation(root, manifest)
            operator_tools, bundle = observe_projections(root)
            observation = make_candidate_observation(
                root,
                manifest,
                command,
                dry_run,
                runtime,
                operator_tools,
                bundle,
            )
            # Candidate output is always one canonical subordinate observation. It is explicitly
            # unadmitted and non-authoritative; only the external release-candidate bridge may
            # validate it and render a final admitted v2 human or JSON report.
            sys.stdout.write(canonical_json(observation))
            return 0
        policy = load_policy(root)
        checkout = load_checkout(root)
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
        operator_tools, bundle = observe_projections(root)
        report = make_report(
            policy,
            command,
            dry_run,
            checkout,
            runtime,
            operator_tools,
            bundle,
            [],
            exit_class="ok",
        )
        emit(report, json_output)
        return 0
    except (ReportInvariantError, OSError, ValueError) as exc:
        if candidate_mode:
            print(f"candidate subordinate observation refused: {exc}", file=sys.stderr)
            return 3
        print(f"internal report construction invariant failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
