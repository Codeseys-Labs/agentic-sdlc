#!/usr/bin/env python3
"""Read-only checkout-development evidence behind ``ccodex sdlc``.

The installed dispatcher invokes this file with its install-bound, UV-managed Python 3.12.11 using
``-I -B``.  It is intentionally not a lifecycle surface: it reads existing state, never creates or
repairs it, and renders one closed semantic report in either human or canonical JSON form.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
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
    "version": "0.7.3",
}


class UsageError(ValueError):
    pass


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


def parse_command(argv: list[str]) -> tuple[str, bool, bool]:
    if argv in (["-h"], ["--help"], ["help"]):
        raise UsageError("help")
    if not argv:
        raise UsageError("ccodex sdlc needs inspect, status, doctor, or recover --dry-run")
    verb = argv[0]
    if verb not in {"inspect", "status", "doctor", "recover"}:
        raise UsageError(f"unknown ccodex sdlc verb: {verb}")
    rest = argv[1:]
    if verb == "recover":
        if rest == ["--dry-run"]:
            return verb, True, False
        if rest == ["--dry-run", "--json"]:
            return verb, True, True
        raise UsageError("ccodex sdlc recover requires exactly --dry-run, optionally followed by --json")
    if rest == []:
        return verb, False, False
    if rest == ["--json"]:
        return verb, False, True
    raise UsageError(f"ccodex sdlc {verb} accepts only optional --json")


def usage() -> str:
    return (
        "usage: ccodex sdlc inspect [--json]\n"
        "       ccodex sdlc status [--json]\n"
        "       ccodex sdlc doctor [--json]\n"
        "       ccodex sdlc recover --dry-run [--json]\n\n"
        "Read checkout-development ownership and recovery evidence without installing, updating,\n"
        "uninstalling, following, or changing state. `recover` is proposal-only and requires\n"
        "the literal --dry-run safeguard.\n"
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
        command, dry_run, json_output = parse_command(selected)
    except UsageError as exc:
        if str(exc) == "help":
            sys.stdout.write(usage())
            return 0
        print(f"error: {exc}\n\n{usage()}", file=sys.stderr, end="")
        return 2

    root = Path(__file__).parent.parent
    try:
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
        print(f"internal report construction invariant failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
