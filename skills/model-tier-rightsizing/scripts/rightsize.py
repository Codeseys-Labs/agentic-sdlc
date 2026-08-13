#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build deterministic, evidence-backed model-task maps.

Live evaluation is intentionally explicit: ``plan`` produces an authorization digest and
``evaluate`` accepts only that exact digest. Generated artifacts contain measurements and
digests, never task prompts, model output, credentials, PII, or mutable absolute paths.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
POLICY_PATH = SKILL_ROOT / "policy" / "rightsize-evaluation-v1.json"
TASK_POLICY_PATH = SKILL_ROOT / "policy" / "rightsize-task-pack-v1.json"
RUNTIME_POLICY_PATH = SKILL_ROOT / "policy" / "runtime-assignment-receipt-v1.json"
DEFAULT_PACK_PATH = SKILL_ROOT / "evaluations" / "harness-smoke-v1.json"
BENCHMARK_PATH = SKILL_ROOT / "references" / "model-benchmark-evidence-2026-08-12.json"
LAUNCHER_PATH = REPO_ROOT / "scripts" / "opencodex-claude.sh"
EVALUATOR_PATH = Path(__file__).resolve()
GATEWAY_ENDPOINT = "http://127.0.0.1:10100/v1/models"
EVALUATOR_VERSION = "rightsize-evaluator/1"

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


CLASSIFICATIONS: dict[str, dict[str, str]] = {
    "mechanical_redo": {
        "blast_radius": "local/reversible",
        "determinism_of_gate": "complete",
        "scope_of_mutation": "one bounded artifact",
        "authority_proximity": "none",
        "corpus_size": "small",
        "dependency_fanout": "none",
    },
    "deterministic_gated_change": {
        "blast_radius": "contained/visible",
        "determinism_of_gate": "compiler, test, schema, or exact diff",
        "scope_of_mutation": "isolated files",
        "authority_proximity": "low",
        "corpus_size": "small/medium",
        "dependency_fanout": "low",
    },
    "evidence_extraction": {
        "blast_radius": "contained/visible",
        "determinism_of_gate": "evidence coverage or schema",
        "scope_of_mutation": "read-only",
        "authority_proximity": "low",
        "corpus_size": "medium/large",
        "dependency_fanout": "low",
    },
    "repository_discovery": {
        "blast_radius": "contained semantic omission",
        "determinism_of_gate": "partitioned evidence inventory",
        "scope_of_mutation": "read-only",
        "authority_proximity": "low",
        "corpus_size": "large",
        "dependency_fanout": "medium",
    },
    "semantic_implementation": {
        "blast_radius": "contained silent degradation",
        "determinism_of_gate": "partial; immutable review required",
        "scope_of_mutation": "interacting bounded change",
        "authority_proximity": "medium",
        "corpus_size": "medium",
        "dependency_fanout": "medium",
    },
    "semantic_review": {
        "blast_radius": "contained silent acceptance",
        "determinism_of_gate": "explicit criteria plus independent review",
        "scope_of_mutation": "immutable candidate",
        "authority_proximity": "medium",
        "corpus_size": "medium",
        "dependency_fanout": "medium",
    },
    "integration_reconcile": {
        "blast_radius": "cross-branch or contract damage",
        "determinism_of_gate": "re-gate on immutable integration head",
        "scope_of_mutation": "multi-component fan-in",
        "authority_proximity": "high",
        "corpus_size": "large",
        "dependency_fanout": "high",
    },
    "authority_or_frontier": {
        "blast_radius": "derail, trust, credential, data-loss, or settled-truth error",
        "determinism_of_gate": "fail closed plus re-derivation",
        "scope_of_mutation": "advisory only",
        "authority_proximity": "direct",
        "corpus_size": "large when needed",
        "dependency_fanout": "high",
    },
}

REQUIRED_RUN_SPEC_FIELDS = {
    "schema_version",
    "routes",
    "task_classes",
    "task_pack",
    "evaluation_depth",
    "pareto_objective",
    "attempts_per_task",
    "budgets",
    "expected_peak_input_tokens",
    "allow_usage_credits",
    "target_data_egress_acknowledged",
    "output",
    "regenerate",
    "force",
}

REQUIRED_ROUTE_FIELDS = {
    "transport_surface",
    "route_kind",
    "provider",
    "auth_basis",
    "billing_basis",
    "requested_model_id",
    "requested_effort",
    "requested_context_form",
}

PROBE_TASK = {
    "id": "route-probe",
    "task_class": "__route_probe__",
    "critical": False,
    "prompt": "Return exactly RIGHTSIZE_ROUTE_OK and nothing else.",
    "expected_peak_input_tokens": 32,
    "output_reserve_tokens": 16,
    "tools": [],
    "verifier": {"type": "exact", "expected": "RIGHTSIZE_ROUTE_OK"},
}


class RightsizeError(Exception):
    """A named fail-closed evaluation refusal."""


def parse_no_duplicate_members(raw: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RightsizeError(f"duplicate-json-member:{key}")
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise RightsizeError(f"invalid-json:{exc.msg}") from exc


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def load_json(path: Path) -> Any:
    try:
        return parse_no_duplicate_members(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RightsizeError(f"unreadable-json:{path.name}:{exc.strerror}") from exc


def utc_timestamp(timestamp: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if timestamp is None else timestamp))


def default_runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False, **kwargs)


def run_checked(
    argv: list[str],
    *,
    runner: CommandRunner = default_runner,
    cwd: Path | None = None,
    timeout: int = 15,
    env: dict[str, str] | None = None,
    label: str,
) -> str:
    try:
        result = runner(argv, cwd=cwd, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RightsizeError(f"{label}-unavailable:{type(exc).__name__}") from exc
    if result.returncode != 0:
        raise RightsizeError(f"{label}-failed:{result.returncode}")
    return result.stdout


def repository_identity(target: Path, runner: CommandRunner = default_runner) -> tuple[Path, str]:
    resolved = target.expanduser().resolve()
    if not resolved.is_dir():
        raise RightsizeError("target-not-readable-directory")
    top = run_checked(
        ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
        runner=runner,
        label="target-repository",
    ).strip()
    commit = run_checked(
        ["git", "-C", str(resolved), "rev-parse", "HEAD"],
        runner=runner,
        label="target-head",
    ).strip()
    root = Path(top).resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise RightsizeError("target-outside-repository") from exc
    return resolved, digest({"commit": commit, "relative_target": relative})


def fetch_catalog(timeout: int = 5) -> bytes:
    request = Request(GATEWAY_ENDPOINT, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed loopback endpoint
            if response.status != 200:
                raise RightsizeError(f"gateway-catalog-http:{response.status}")
            return response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RightsizeError(f"gateway-catalog-unavailable:{type(exc).__name__}") from exc


def catalog_ids(raw: bytes) -> list[str]:
    try:
        parsed = parse_no_duplicate_members(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RightsizeError("gateway-catalog-not-utf8") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), list):
        raise RightsizeError("gateway-catalog-malformed")
    ids = [row.get("id") for row in parsed["data"] if isinstance(row, dict)]
    if any(not isinstance(model_id, str) or not model_id for model_id in ids):
        raise RightsizeError("gateway-catalog-malformed-id")
    return sorted(set(ids))


def configured_providers(raw: str) -> list[str]:
    providers: list[str] = []
    in_configured = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped == "Configured providers:":
            in_configured = True
            continue
        if stripped.startswith("Available from registry"):
            break
        if in_configured and stripped:
            provider = stripped.split()[0]
            if provider not in providers:
                providers.append(provider)
    return providers


def registry_providers(raw: str) -> list[str]:
    providers: list[str] = []
    in_registry = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("Available from registry"):
            in_registry = True
            continue
        if in_registry and stripped:
            provider = stripped.split()[0]
            if provider not in providers:
                providers.append(provider)
    return providers


def sanitize_auth(raw: str) -> dict[str, Any]:
    value = parse_no_duplicate_members(raw)
    if not isinstance(value, dict):
        raise RightsizeError("claude-auth-malformed")
    return {
        "logged_in": value.get("loggedIn") is True,
        "auth_method": value.get("authMethod") if isinstance(value.get("authMethod"), str) else "unavailable",
        "api_provider": value.get("apiProvider") if isinstance(value.get("apiProvider"), str) else "unavailable",
        "subscription_type": value.get("subscriptionType")
        if isinstance(value.get("subscriptionType"), str)
        else "unavailable",
    }


def parse_live_models(raw: str) -> list[dict[str, Any]]:
    value = parse_no_duplicate_members(raw)
    if not isinstance(value, list):
        raise RightsizeError("live-models-malformed")
    models: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict):
            raise RightsizeError("live-models-malformed-row")
        exact_id = row.get("namespaced") or row.get("id")
        provider = row.get("provider")
        if not isinstance(exact_id, str) or not isinstance(provider, str):
            raise RightsizeError("live-models-missing-identity")
        efforts = row.get("reasoningEfforts", [])
        if not isinstance(efforts, list) or any(not isinstance(item, str) for item in efforts):
            raise RightsizeError(f"live-models-bad-effort:{exact_id}")
        context = row.get("contextWindow")
        models.append(
            {
                "exact_model_id": exact_id,
                "provider": provider,
                "effort_vocab": efforts,
                "reported_context_tokens": context if isinstance(context, int) and context > 0 else None,
                "disabled": row.get("disabled") is True,
            }
        )
    return sorted(models, key=lambda row: (row["provider"], row["exact_model_id"]))


def discover(
    target: Path,
    *,
    runner: CommandRunner = default_runner,
    catalog_raw: bytes | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    _, target_digest = repository_identity(target, runner)
    raw_catalog = fetch_catalog() if catalog_raw is None else catalog_raw
    ids = catalog_ids(raw_catalog)
    live_raw = run_checked(
        ["mise", "-C", str(REPO_ROOT), "exec", "--", "ocx", "models", "live", "--json"],
        runner=runner,
        label="ocx-live-models",
    )
    provider_raw = run_checked(
        ["mise", "-C", str(REPO_ROOT), "exec", "--", "ocx", "provider", "list"],
        runner=runner,
        label="ocx-provider-list",
    )
    auth_raw = run_checked(
        ["claude", "auth", "status", "--json"],
        runner=runner,
        label="claude-auth-status",
    )
    runtime_policy = load_json(RUNTIME_POLICY_PATH)
    claude_ids = sorted(
        model_id
        for model_id, provider in runtime_policy["allowed_exact_model_ids"].items()
        if provider == "anthropic"
    )
    live_models = parse_live_models(live_raw)
    live_providers = sorted({row["provider"] for row in live_models if not row["disabled"]})
    auth = sanitize_auth(auth_raw)
    return {
        "schema_version": "rightsize-discovery/v1",
        "captured_at": captured_at or utc_timestamp(),
        "target_identity_sha256": target_digest,
        "gateway": {
            "endpoint": GATEWAY_ENDPOINT,
            "live": True,
            "catalog_sha256": digest_bytes(raw_catalog),
            "catalog_ids": ids,
        },
        "configured_providers": configured_providers(provider_raw),
        "registry_providers": registry_providers(provider_raw),
        "live_providers": live_providers,
        "live_models": live_models,
        "claude_subscription": {
            **auth,
            "usable": auth["logged_in"]
            and auth["auth_method"] == "claude.ai"
            and auth["api_provider"] == "firstParty",
            "candidate_exact_model_ids": claude_ids,
        },
    }


def load_spec(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = parse_no_duplicate_members(raw)
    if not isinstance(value, dict):
        raise RightsizeError("run-spec-not-object")
    return value


def ensure_exact_fields(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        raise RightsizeError(f"question-required:{label}.{missing[0]}")
    if extra:
        raise RightsizeError(f"unknown-field:{label}.{extra[0]}")


def validate_positive_number(value: Any, label: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RightsizeError(f"invalid-number:{label}")
    if value <= 0 or value > maximum:
        raise RightsizeError(f"out-of-range:{label}")
    return float(value)


def validate_spec(spec: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    ensure_exact_fields(spec, REQUIRED_RUN_SPEC_FIELDS, "spec")
    if spec["schema_version"] != policy["run_spec_schema_version"]:
        raise RightsizeError("unsupported-run-spec-version")
    if not isinstance(spec["routes"], list) or not spec["routes"]:
        raise RightsizeError("question-required:spec.routes")
    routes: list[dict[str, Any]] = []
    seen_routes: set[tuple[str, str, str]] = set()
    for index, route in enumerate(spec["routes"]):
        if not isinstance(route, dict):
            raise RightsizeError(f"invalid-route:{index}")
        ensure_exact_fields(route, REQUIRED_ROUTE_FIELDS, f"route[{index}]")
        if route["transport_surface"] != "claude-code-gateway":
            raise RightsizeError(f"unsupported-transport:{index}")
        if route["route_kind"] not in policy["route_kinds"]:
            raise RightsizeError(f"unsupported-route-kind:{index}")
        for field in ("provider", "auth_basis", "billing_basis", "requested_model_id"):
            if not isinstance(route[field], str) or not route[field]:
                raise RightsizeError(f"invalid-route-field:{index}.{field}")
        if route["auth_basis"] not in policy["auth_bases"]:
            raise RightsizeError(f"unsupported-auth-basis:{index}")
        if route["billing_basis"] not in policy["billing_bases"]:
            raise RightsizeError(f"unsupported-billing-basis:{index}")
        if route["route_kind"] == "gateway-claude-subscription-passthrough" and (
            route["provider"] != "anthropic"
            or route["auth_basis"] != "operator-claude-login"
            or route["billing_basis"] != "claude-subscription"
        ):
            raise RightsizeError(f"invalid-claude-passthrough-basis:{index}")
        if route["requested_effort"] not in policy["allowed_efforts"]:
            raise RightsizeError(f"unsupported-effort:{index}")
        if route["requested_context_form"] not in policy["allowed_context_forms"]:
            raise RightsizeError(f"unsupported-context-form:{index}")
        key = (route["requested_model_id"], route["requested_effort"], route["requested_context_form"])
        if key in seen_routes:
            raise RightsizeError(f"duplicate-route:{index}")
        seen_routes.add(key)
        routes.append(copy.deepcopy(route))

    classes = spec["task_classes"]
    if not isinstance(classes, list) or not classes:
        raise RightsizeError("question-required:spec.task_classes")
    if any(task_class not in policy["task_classes"] for task_class in classes):
        raise RightsizeError("unknown-task-class")
    if len(set(classes)) != len(classes):
        raise RightsizeError("duplicate-task-class")
    if spec["evaluation_depth"] not in policy["evaluation_depths"]:
        raise RightsizeError("unsupported-evaluation-depth")
    if spec["pareto_objective"] not in policy["pareto_objectives"]:
        raise RightsizeError("unsupported-pareto-objective")
    if not isinstance(spec["task_pack"], str) or not spec["task_pack"]:
        raise RightsizeError("question-required:spec.task_pack")
    if not isinstance(spec["attempts_per_task"], int) or isinstance(spec["attempts_per_task"], bool):
        raise RightsizeError("invalid-attempts-per-task")
    if spec["attempts_per_task"] < 1 or spec["attempts_per_task"] > 100:
        raise RightsizeError("out-of-range:attempts-per-task")
    if not isinstance(spec["budgets"], dict) or set(spec["budgets"]) != {
        "max_calls",
        "max_wall_seconds",
        "max_api_equivalent_usd",
    }:
        raise RightsizeError("invalid-budgets")
    for field, maximum in policy["budget_limits"].items():
        validate_positive_number(spec["budgets"][field], f"budgets.{field}", maximum)
    if not isinstance(spec["budgets"]["max_calls"], int):
        raise RightsizeError("invalid-number:budgets.max_calls")
    if not isinstance(spec["expected_peak_input_tokens"], int) or spec["expected_peak_input_tokens"] < 0:
        raise RightsizeError("invalid-expected-peak-input")
    for field in (
        "allow_usage_credits",
        "target_data_egress_acknowledged",
        "regenerate",
        "force",
    ):
        if not isinstance(spec[field], bool):
            raise RightsizeError(f"invalid-boolean:{field}")
    if spec["force"] and not spec["regenerate"]:
        raise RightsizeError("force-requires-regenerate")
    if not isinstance(spec["output"], str) or not spec["output"].endswith(".json"):
        raise RightsizeError("output-must-be-json")

    normalized = copy.deepcopy(spec)
    normalized["routes"] = sorted(
        routes,
        key=lambda route: (
            route["provider"],
            route["requested_model_id"],
            route["requested_effort"],
            route["requested_context_form"],
        ),
    )
    normalized["task_classes"] = [item for item in policy["task_classes"] if item in classes]
    return normalized


def resolve_pack_path(spec_path: str, target_root: Path) -> Path:
    if spec_path == "builtin:harness-smoke-v1":
        return DEFAULT_PACK_PATH
    path = Path(spec_path).expanduser()
    if not path.is_absolute():
        path = target_root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(target_root.resolve())
    except ValueError as exc:
        raise RightsizeError("task-pack-outside-target") from exc
    return resolved


def validate_fixture(root: Path) -> None:
    if root.is_symlink():
        raise RightsizeError(f"fixture-symlink-forbidden:{root.name}")
    if not root.is_dir():
        raise RightsizeError("fixture-not-directory")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RightsizeError(f"fixture-symlink-forbidden:{path.name}")
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise RightsizeError(f"fixture-escape:{path.name}") from exc


def fixture_digest(root: Path) -> str:
    validate_fixture(root)
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append({"path": relative, "kind": "directory"})
        elif path.is_file():
            entries.append({"path": relative, "kind": "file", "sha256": digest_bytes(path.read_bytes())})
        else:
            raise RightsizeError(f"fixture-special-file-forbidden:{path.name}")
    return digest(entries)


def validate_verifier(verifier: Any, task_id: str, evaluation_policy: dict[str, Any]) -> None:
    if not isinstance(verifier, dict) or verifier.get("type") not in evaluation_policy["verifier_types"]:
        raise RightsizeError(f"unsupported-verifier:{task_id}")
    kind = verifier["type"]
    required_fields = {
        "exact": {"type", "expected"},
        "schema": {"type", "required", "properties"},
        "finding-coverage": {"type", "required_findings"},
        "file-diff": {"type", "sha256"},
    }[kind]
    if set(verifier) != required_fields:
        raise RightsizeError(f"invalid-verifier-fields:{task_id}")
    if kind == "exact":
        if not isinstance(verifier["expected"], str):
            raise RightsizeError(f"invalid-verifier:{task_id}")
        return
    if kind == "schema":
        required = verifier["required"]
        properties = verifier["properties"]
        allowed_types = {"string", "integer", "number", "boolean", "object", "array"}
        if (
            not isinstance(required, list)
            or any(not isinstance(field, str) or not field for field in required)
            or len(set(required)) != len(required)
            or not isinstance(properties, dict)
            or any(
                not isinstance(field, str) or not field or expected not in allowed_types
                for field, expected in properties.items()
            )
            or any(field not in properties for field in required)
        ):
            raise RightsizeError(f"invalid-verifier:{task_id}")
        return
    if kind == "finding-coverage":
        findings = verifier["required_findings"]
        if (
            not isinstance(findings, list)
            or not findings
            or any(not isinstance(finding, str) or not finding for finding in findings)
        ):
            raise RightsizeError(f"invalid-verifier:{task_id}")
        return
    if kind == "file-diff":
        expected = verifier["sha256"]
        if not isinstance(expected, dict) or not expected:
            raise RightsizeError(f"invalid-verifier:{task_id}")
        for relative, expected_digest in expected.items():
            path = Path(relative) if isinstance(relative, str) else Path()
            if (
                not isinstance(relative, str)
                or not relative
                or path.is_absolute()
                or ".." in path.parts
                or not isinstance(expected_digest, str)
                or len(expected_digest) != 64
                or any(character not in "0123456789abcdef" for character in expected_digest)
            ):
                raise RightsizeError(f"invalid-verifier:{task_id}")
        return


def validate_task_pack(pack: dict[str, Any], pack_path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    required = set(policy["required_top_level_fields"])
    ensure_exact_fields(pack, required, "task-pack")
    if pack["schema_version"] != policy["task_pack_schema_version"]:
        raise RightsizeError("unsupported-task-pack-version")
    if pack["kind"] not in policy["kinds"]:
        raise RightsizeError("unsupported-task-pack-kind")
    if pack["harness_profile"] not in policy["harness_profiles"]:
        raise RightsizeError("unsupported-harness-profile")
    if pack["runtime_profile"] not in policy["runtime_profiles"]:
        raise RightsizeError("unsupported-runtime-profile")
    if pack["data_classification"] not in policy["data_classifications"]:
        raise RightsizeError("unsupported-data-classification")
    if not isinstance(pack["target_representative"], bool):
        raise RightsizeError("invalid-target-representative")
    if not isinstance(pack["expected_results_hidden_or_immutable"], bool):
        raise RightsizeError("invalid-expected-results-boundary")
    if not isinstance(pack["id"], str) or not pack["id"]:
        raise RightsizeError("invalid-task-pack-id")
    if not isinstance(pack["tasks"], list) or not pack["tasks"]:
        raise RightsizeError("empty-task-pack")
    task_ids: set[str] = set()
    normalized = copy.deepcopy(pack)
    optional = set(policy.get("task_optional_fields", []))
    evaluation_policy = load_json(POLICY_PATH)
    for index, task in enumerate(normalized["tasks"]):
        if not isinstance(task, dict):
            raise RightsizeError(f"invalid-task:{index}")
        required = set(policy["task_required_fields"])
        missing = sorted(required - set(task))
        extra = sorted(set(task) - required - optional)
        if missing:
            raise RightsizeError(f"question-required:task[{index}].{missing[0]}")
        if extra:
            raise RightsizeError(f"unknown-field:task[{index}].{extra[0]}")
        if not isinstance(task["id"], str) or not task["id"] or task["id"] in task_ids:
            raise RightsizeError(f"invalid-task-id:{index}")
        task_ids.add(task["id"])
        if task["task_class"] not in CLASSIFICATIONS:
            raise RightsizeError(f"unknown-task-class:{task['id']}")
        if not isinstance(task["critical"], bool) or not isinstance(task["prompt"], str) or not task["prompt"]:
            raise RightsizeError(f"invalid-task-metadata:{task['id']}")
        for token_field in ("expected_peak_input_tokens", "output_reserve_tokens"):
            if not isinstance(task[token_field], int) or task[token_field] < 0:
                raise RightsizeError(f"invalid-task-token-budget:{task['id']}")
        fixture = task.get("fixture")
        if fixture is not None:
            if not isinstance(fixture, str) or not fixture or Path(fixture).is_absolute():
                raise RightsizeError(f"invalid-task-fixture:{task['id']}")
            source = (pack_path.parent / fixture).resolve()
            try:
                source.relative_to(pack_path.parent.resolve())
            except ValueError as exc:
                raise RightsizeError(f"fixture-outside-pack:{task['id']}") from exc
            task["fixture_sha256"] = fixture_digest(source)
        tools = task["tools"]
        if not isinstance(tools, list) or any(tool not in evaluation_policy["allowed_model_tools"] for tool in tools):
            raise RightsizeError(f"unsupported-task-tool:{task['id']}")
        validate_verifier(task["verifier"], task["id"], evaluation_policy)
    return normalized


def runtime_admission(route: dict[str, Any], runtime_policy: dict[str, Any]) -> bool:
    model = route["requested_model_id"]
    provider = runtime_policy["allowed_exact_model_ids"].get(model)
    tuple_value = [model, route["requested_effort"], route["requested_context_form"]]
    return provider == route["provider"] and tuple_value in runtime_policy["certified_request_tuples"]


def needs_usage_credit_ack(route: dict[str, Any], policy: dict[str, Any]) -> bool:
    if route["route_kind"] != "gateway-claude-subscription-passthrough":
        return False
    rules = policy["claude_usage_credit_acknowledgement_required_for"]
    return route["requested_context_form"] in rules["context_forms"] or any(
        route["requested_model_id"].startswith(prefix) for prefix in rules["model_prefixes"]
    )


def route_discovery_state(
    route: dict[str, Any], discovery: dict[str, Any], runtime_policy: dict[str, Any]
) -> dict[str, Any]:
    model_id = route["requested_model_id"]
    if route["route_kind"] == "gateway-routed-provider":
        live = next(
            (row for row in discovery["live_models"] if row["exact_model_id"] == model_id and not row["disabled"]),
            None,
        )
        catalog_present = model_id in discovery["gateway"]["catalog_ids"]
        blockers: list[str] = []
        if route["provider"] not in discovery["configured_providers"]:
            blockers.append("provider-not-configured")
        if route["provider"] not in discovery["live_providers"]:
            blockers.append("provider-not-live")
        if live is None:
            blockers.append("exact-model-not-live")
        if not catalog_present:
            blockers.append("exact-model-not-in-raw-catalog")
        if live is not None and live["provider"] != route["provider"]:
            blockers.append("provider-mismatch")
        if live is not None and route["requested_effort"] not in live["effort_vocab"]:
            blockers.append("effort-not-observed")
        return {
            "catalog_present": catalog_present,
            "live": live is not None,
            "effort_vocab": [] if live is None else live["effort_vocab"],
            "effort_vocab_source": "ocx-live-models" if live is not None else "unavailable",
            "reported_context_tokens": None if live is None else live["reported_context_tokens"],
            "runtime_policy_admitted": runtime_admission(route, runtime_policy),
            "blockers": blockers,
        }

    auth = discovery["claude_subscription"]
    blockers = []
    if not auth["usable"]:
        blockers.append("claude-subscription-not-usable")
    if model_id not in auth["candidate_exact_model_ids"]:
        blockers.append("claude-exact-id-not-admitted")
    if not model_id.startswith("claude-"):
        blockers.append("claude-alias-forbidden")
    if route["provider"] != "anthropic":
        blockers.append("provider-mismatch")
    return {
        "catalog_present": model_id in auth["candidate_exact_model_ids"],
        "live": auth["usable"],
        "effort_vocab": [],
        "effort_vocab_source": "unavailable",
        "requested_effort_policy_admitted": [
            model_id,
            route["requested_effort"],
            route["requested_context_form"],
        ]
        in runtime_policy["certified_request_tuples"],
        "reported_context_tokens": None,
        "runtime_policy_admitted": runtime_admission(route, runtime_policy),
        "blockers": blockers,
    }


def context_state(
    route: dict[str, Any], route_state: dict[str, Any], required_tokens: int, policy: dict[str, Any]
) -> dict[str, Any]:
    margin = math.ceil(required_tokens * policy["context"]["safety_margin_ratio"])
    needed = required_tokens + margin
    if route["requested_context_form"] == "[1m]":
        ceiling = (
            policy["context"]["extended_context_tokens"]
            if route_state["runtime_policy_admitted"]
            else None
        )
        source = "runtime-policy-certified-request-form" if ceiling is not None else "uncertified-request-form"
    elif route["route_kind"] == "gateway-claude-subscription-passthrough":
        ceiling = policy["context"]["claude_declared_base_tokens"].get(route["requested_model_id"])
        source = "checked-in-provider-declared-base" if ceiling is not None else "unavailable"
    else:
        ceiling = route_state["reported_context_tokens"]
        source = "ocx-live-models"
    return {
        "required_tokens_with_margin": needed,
        "requested_capacity_ceiling": ceiling,
        "capacity_source": source,
        "fits": isinstance(ceiling, int) and needed <= ceiling,
        "served_context_readback": "unavailable",
    }


def plan_run(
    spec: dict[str, Any],
    discovery: dict[str, Any],
    target_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_json(POLICY_PATH)
    task_policy = load_json(TASK_POLICY_PATH)
    runtime_policy = load_json(RUNTIME_POLICY_PATH)
    normalized = validate_spec(spec, policy)
    output_path = artifact_paths(target_root, normalized["output"])[0]
    normalized["output"] = output_path.relative_to(target_root.resolve()).as_posix()
    if normalized["evaluation_depth"] == "probe":
        pack_path = DEFAULT_PACK_PATH
        pack = {
            "schema_version": task_policy["task_pack_schema_version"],
            "id": "route-probe-v1",
            "kind": "harness-smoke",
            "harness_profile": "claude-code-print-v1",
            "runtime_profile": "no-tools",
            "target_representative": False,
            "expected_results_hidden_or_immutable": False,
            "data_classification": "synthetic",
            "tasks": [copy.deepcopy(PROBE_TASK)],
        }
        normalized["task_pack"] = "builtin:route-probe-v1"
        selected_tasks = pack["tasks"]
        planned_attempts = 1
    else:
        pack_path = resolve_pack_path(normalized["task_pack"], target_root)
        pack = validate_task_pack(load_json(pack_path), pack_path, task_policy)
        if normalized["task_pack"] != "builtin:harness-smoke-v1":
            normalized["task_pack"] = pack_path.relative_to(target_root.resolve()).as_posix()
        selected_tasks = [task for task in pack["tasks"] if task["task_class"] in normalized["task_classes"]]
        planned_attempts = normalized["attempts_per_task"]
        if not selected_tasks:
            raise RightsizeError("task-pack-has-no-selected-classes")
    if pack["data_classification"] == "target-content" and not normalized["target_data_egress_acknowledged"]:
        raise RightsizeError("question-required:target_data_egress_acknowledged")
    qualification = policy["qualification"]
    if normalized["evaluation_depth"] == "qualification":
        if (
            pack["kind"] != "target-representative"
            or not pack["target_representative"]
            or not pack["expected_results_hidden_or_immutable"]
        ):
            raise RightsizeError("qualification-requires-target-representative-pack")
        counts: dict[str, int] = {}
        for task in selected_tasks:
            counts[task["task_class"]] = counts.get(task["task_class"], 0) + 1
        if any(counts.get(task_class, 0) < qualification["minimum_distinct_tasks"] for task_class in normalized["task_classes"]):
            raise RightsizeError("qualification-insufficient-distinct-tasks")
        if normalized["attempts_per_task"] < qualification["minimum_attempts_per_task"]:
            raise RightsizeError("qualification-insufficient-attempts")
        if any(
            task["task_class"] == "authority_or_frontier" and not task["critical"]
            for task in selected_tasks
        ):
            raise RightsizeError("authority-or-frontier-task-must-be-critical")
    if any(needs_usage_credit_ack(route, policy) for route in normalized["routes"]) and not normalized["allow_usage_credits"]:
        raise RightsizeError("question-required:allow_usage_credits")

    max_pack_requirement = max(
        task["expected_peak_input_tokens"] + task["output_reserve_tokens"] for task in selected_tasks
    )
    required_tokens = max(normalized["expected_peak_input_tokens"], max_pack_requirement)
    route_plans: list[dict[str, Any]] = []
    for route in normalized["routes"]:
        state = route_discovery_state(route, discovery, runtime_policy)
        context = context_state(route, state, required_tokens, policy)
        blockers = list(state["blockers"])
        if not context["fits"]:
            blockers.append("context-requirement-not-met")
        route_plans.append(
            {
                "route": route,
                "discovery_state": state,
                "context_state": context,
                "evaluation_eligible": not blockers,
                "blockers": blockers,
            }
        )
    eligible = [route for route in route_plans if route["evaluation_eligible"]]
    if not eligible:
        raise RightsizeError("no-evaluation-eligible-route")
    call_count = len(eligible) * len(selected_tasks) * planned_attempts
    if call_count > normalized["budgets"]["max_calls"]:
        raise RightsizeError("budget-max-calls-too-small")

    pack_summary = {
        "id": pack["id"],
        "kind": pack["kind"],
        "harness_profile": pack["harness_profile"],
        "runtime_profile": pack["runtime_profile"],
        "target_representative": pack["target_representative"],
        "data_classification": pack["data_classification"],
        "task_count": len(selected_tasks),
        "task_ids": [task["id"] for task in selected_tasks],
        "task_pack_sha256": digest(pack),
    }
    benchmark_digest = digest_bytes(BENCHMARK_PATH.read_bytes()) if BENCHMARK_PATH.exists() else "unavailable"
    authorization = {
        "schema_version": "rightsize-authorization/v1",
        "evaluator_version": EVALUATOR_VERSION,
        "evaluator_sha256": digest_bytes(EVALUATOR_PATH.read_bytes()),
        "evaluation_policy_sha256": digest_bytes(POLICY_PATH.read_bytes()),
        "task_pack_policy_sha256": digest_bytes(TASK_POLICY_PATH.read_bytes()),
        "runtime_policy_sha256": digest_bytes(RUNTIME_POLICY_PATH.read_bytes()),
        "launcher_sha256": digest_bytes(LAUNCHER_PATH.read_bytes()),
        "target_identity_sha256": discovery["target_identity_sha256"],
        "catalog_sha256": discovery["gateway"]["catalog_sha256"],
        "discovery_snapshot": {
            "configured_providers": discovery["configured_providers"],
            "registry_providers": discovery.get("registry_providers", []),
            "live_providers": discovery["live_providers"],
            "live_models": discovery["live_models"],
            "claude_subscription": discovery["claude_subscription"],
        },
        "route_plans": route_plans,
        "run_spec_sha256": digest(normalized),
        "task_pack_sha256": pack_summary["task_pack_sha256"],
        "benchmark_snapshot_sha256": benchmark_digest,
        "eligible_routes": [route["route"] for route in eligible],
        "blocked_routes": [
            {"route": route["route"], "blockers": route["blockers"]}
            for route in route_plans
            if not route["evaluation_eligible"]
        ],
        "task_ids": pack_summary["task_ids"],
        "attempts_per_task": planned_attempts,
        "exact_model_calls": call_count,
        "budgets": normalized["budgets"],
        "data_classification": pack["data_classification"],
        "data_egress_destination": "selected model providers",
        "output": normalized["output"],
        "stop_conditions": [
            "any route or identity mismatch",
            "model-call, wall-time, or API-equivalent-cost budget exhausted",
            "context admission failure",
            "malformed or ungradable output",
        ],
    }
    plan = {
        "schema_version": "rightsize-plan/v1",
        "authorization_digest": digest(authorization),
        "authorization": authorization,
        "run_spec": normalized,
        "task_pack": pack_summary,
        "routes": route_plans,
        "live_calls_made": False,
        "files_written": False,
    }
    execution = {"pack": pack, "pack_path": pack_path, "tasks": selected_tasks, "eligible": eligible}
    return plan, execution


def wire_model_id(route: dict[str, Any]) -> str:
    suffix = "[1m]" if route["requested_context_form"] == "[1m]" else ""
    return route["requested_model_id"] + suffix


def capture_logs(runner: CommandRunner = default_runner) -> list[dict[str, Any]]:
    raw = run_checked(
        ["mise", "-C", str(REPO_ROOT), "exec", "--", "ocx", "observe", "logs", "--jsonl"],
        runner=runner,
        timeout=20,
        label="ocx-attribution-logs",
    )
    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        value = parse_no_duplicate_members(line)
        if isinstance(value, dict) and isinstance(value.get("requestId"), str):
            records.append(value)
    return records


def task_workspace(task: dict[str, Any], pack_path: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="rightsize-")
    workspace = Path(temporary.name)
    fixture = task.get("fixture")
    if fixture is not None:
        source = (pack_path.parent / fixture).resolve()
        validate_fixture(source)
        shutil.copytree(source, workspace, dirs_exist_ok=True, symlinks=True)
        if fixture_digest(workspace) != task.get("fixture_sha256"):
            temporary.cleanup()
            raise RightsizeError(f"fixture-changed-during-copy:{task['id']}")
    else:
        (workspace / "README.txt").write_text("Synthetic rightsizing fixture.\n", encoding="utf-8")
    return temporary, workspace


def evaluation_environment() -> dict[str, str]:
    admitted = {
        "HOME",
        "LANG",
        "LC_ALL",
        "LOGNAME",
        "MISE_CACHE_DIR",
        "MISE_CONFIG_DIR",
        "MISE_DATA_DIR",
        "PATH",
        "SHELL",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
    result = {key: value for key, value in os.environ.items() if key in admitted}
    result["PATH"] = result.get("PATH", os.defpath)
    result.setdefault("LANG", "C.UTF-8")
    result["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
    return result


def parse_claude_result(raw: str) -> tuple[str, dict[str, Any]]:
    value = parse_no_duplicate_members(raw)
    if not isinstance(value, dict):
        raise RightsizeError("model-output-envelope-malformed")
    result = value.get("result")
    if not isinstance(result, str):
        raise RightsizeError("model-output-missing-result")
    usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
    return result, {
        "reported_total_cost_usd": value.get("total_cost_usd")
        if isinstance(value.get("total_cost_usd"), (int, float))
        else None,
        "usage": usage,
        "tool_steps": value.get("num_turns") if isinstance(value.get("num_turns"), int) else None,
    }


def new_attempt_records(
    before: Iterable[dict[str, Any]],
    after: Iterable[dict[str, Any]],
    route: dict[str, Any],
    started_ms: int,
    ended_ms: int,
) -> list[dict[str, Any]]:
    old_ids = {record.get("requestId") for record in before}
    accepted_requested = {route["requested_model_id"], wire_model_id(route)}
    return [
        record
        for record in after
        if record.get("requestId") not in old_ids
        and record.get("requestedModel") in accepted_requested
        and isinstance(record.get("timestamp"), int)
        and started_ms - 5000 <= record["timestamp"] <= ended_ms + 5000
    ]


def identity_evidence(route: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    terminal = [record for record in records if record.get("inboundProtocol") == "messages"] or records
    groups = {record.get("conversationId") for record in terminal if record.get("conversationId") is not None}
    if len(groups) > 1 or not terminal:
        return {"verified": False, "failure": "ambiguous-attribution"}
    if any(record.get("status") != 200 for record in terminal):
        return {"verified": False, "failure": "transport-status"}
    excerpts: list[dict[str, Any]] = []
    for record in terminal:
        decision = record.get("routeDecision") if isinstance(record.get("routeDecision"), dict) else {}
        selected = decision.get("selected") if isinstance(decision.get("selected"), dict) else {}
        route_kind = decision.get("routeKind") or record.get("routeKind")
        excerpt = {
            "request_id": record.get("requestId"),
            "requested_model": record.get("requestedModel"),
            "resolved_model": record.get("resolvedModel"),
            "provider": record.get("provider"),
            "status": record.get("status"),
            "route_kind": route_kind,
            "selected_provider": selected.get("provider"),
            "selected_model": selected.get("model"),
        }
        excerpts.append(excerpt)
        if route["route_kind"] == "gateway-routed-provider":
            if route_kind == "default-provider":
                return {"verified": False, "failure": "default-provider", "records": excerpts}
            if record.get("provider") != route["provider"] or selected.get("provider") != route["provider"]:
                return {"verified": False, "failure": "provider-mismatch", "records": excerpts}
            resolved = record.get("resolvedModel")
            selected_model = selected.get("model")
            expected = route["requested_model_id"].split("/", 1)[-1]
            if resolved != expected or selected_model != expected:
                return {"verified": False, "failure": "resolved-model-mismatch", "records": excerpts}
        else:
            if record.get("provider") != "anthropic-native":
                return {"verified": False, "failure": "claude-passthrough-provider-mismatch", "records": excerpts}
    return {
        "verified": True,
        "identity_basis": "gateway_attribution_log"
        if route["route_kind"] == "gateway-routed-provider"
        else "unambiguous_exact_id_mapping_with_provider_attribution",
        "records": excerpts,
    }


def verify_schema(value: Any, verifier: dict[str, Any]) -> bool:
    if not isinstance(value, dict):
        return False
    required = verifier.get("required", [])
    properties = verifier.get("properties", {})
    if not isinstance(required, list) or not isinstance(properties, dict):
        return False
    if any(field not in value for field in required):
        return False
    type_map = {"string": str, "boolean": bool, "object": dict, "array": list}
    for field, expected in properties.items():
        if field not in value:
            continue
        actual = value[field]
        if expected == "integer":
            matches = isinstance(actual, int) and not isinstance(actual, bool)
        elif expected == "number":
            matches = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual)
        else:
            matches = expected in type_map and isinstance(actual, type_map[expected])
        if not matches:
            return False
    return True


def verify_output(output: str, verifier: dict[str, Any], workspace: Path) -> bool:
    kind = verifier["type"]
    if kind == "exact":
        return output.strip() == verifier.get("expected")
    if kind == "schema":
        try:
            return verify_schema(parse_no_duplicate_members(output), verifier)
        except RightsizeError:
            return False
    if kind == "finding-coverage":
        expected = verifier.get("required_findings", [])
        return isinstance(expected, list) and all(isinstance(item, str) and item in output for item in expected)
    if kind == "file-diff":
        expected = verifier.get("sha256", {})
        if not isinstance(expected, dict):
            return False
        for relative, expected_digest in expected.items():
            path = (workspace / relative).resolve()
            try:
                path.relative_to(workspace.resolve())
            except ValueError:
                return False
            if not path.is_file() or digest_bytes(path.read_bytes()) != expected_digest:
                return False
        return True
    return False


def metric_from_records(records: list[dict[str, Any]], name: str) -> int | float | None:
    values = [record.get(name) for record in records if isinstance(record.get(name), (int, float))]
    return sum(values) if values else None


def usage_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    usages = [record.get("usage") for record in records if isinstance(record.get("usage"), dict)]

    def total(*names: str) -> int | None:
        values: list[int] = []
        for usage in usages:
            for name in names:
                value = usage.get(name)
                if isinstance(value, int):
                    values.append(value)
                    break
        return sum(values) if values else None

    input_tokens = total("inputTokens")
    cache_read = total("cacheReadInputTokens", "cachedInputTokens")
    return {
        "input_tokens": input_tokens,
        "uncached_input_tokens": None
        if input_tokens is None or cache_read is None
        else max(0, input_tokens - cache_read),
        "cache_read_tokens": cache_read,
        "cache_write_tokens": total("cacheCreationInputTokens"),
        "reasoning_tokens": total("reasoningOutputTokens"),
        "visible_output_tokens": total("outputTokens"),
        "total_tokens": total("totalTokens"),
    }


def attempt_cost(route: dict[str, Any], records: list[dict[str, Any]], envelope: dict[str, Any]) -> dict[str, Any]:
    costs: list[float] = []
    for record in records:
        display = record.get("displayMetrics") if isinstance(record.get("displayMetrics"), dict) else {}
        cost = display.get("cost") if isinstance(display.get("cost"), dict) else {}
        estimate = cost.get("estimate") if isinstance(cost.get("estimate"), dict) else {}
        total = estimate.get("cost", {}).get("total") if isinstance(estimate.get("cost"), dict) else None
        if isinstance(total, (int, float)):
            costs.append(float(total))
    reported = envelope.get("reported_total_cost_usd")
    api_equivalent = sum(costs) if costs else (float(reported) if isinstance(reported, (int, float)) else None)
    subscription = route["billing_basis"] == "claude-subscription"
    return {
        "marginal_cost_usd": None if subscription else api_equivalent,
        "api_equivalent_cost_usd": api_equivalent,
        "cost_provenance": "subscription-api-equivalent"
        if subscription and api_equivalent is not None
        else "gateway-modeled"
        if costs
        else "client-reported"
        if reported is not None
        else "unavailable",
        "quota_consumption": "unavailable" if subscription else "not-applicable",
        "usage_credits_possible": subscription,
    }


def run_attempt(
    route: dict[str, Any],
    task: dict[str, Any],
    pack_path: Path,
    max_budget_usd: float,
    timeout_seconds: int,
    *,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    before = capture_logs(runner)
    temporary, workspace = task_workspace(task, pack_path)
    started = time.time()
    started_ms = int(started * 1000)
    tools = ",".join(task["tools"])
    argv = [
        str(LAUNCHER_PATH),
        "launch",
        "--",
        "--print",
        "--output-format",
        "json",
        "--safe-mode",
        "--strict-mcp-config",
        "--mcp-config",
        "{}",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--model",
        wire_model_id(route),
        "--effort",
        route["requested_effort"],
        "--tools",
        tools,
        "--max-budget-usd",
        str(max_budget_usd),
    ]
    injection = {
        "schema_version": "rightsize-request-injection/v1",
        "requested_tuple_sha256": digest(
            {
                "model": route["requested_model_id"],
                "effort": route["requested_effort"],
                "context": route["requested_context_form"],
            }
        ),
        "launcher_sha256": digest_bytes(LAUNCHER_PATH.read_bytes()),
        "task_prompt_sha256": digest_bytes(task["prompt"].encode("utf-8")),
    }
    try:
        result = runner(
            argv,
            cwd=workspace,
            timeout=timeout_seconds,
            env=evaluation_environment(),
            input=task["prompt"],
        )
        ended = time.time()
        ended_ms = int(ended * 1000)
        after = capture_logs(runner)
        records = new_attempt_records(before, after, route, started_ms, ended_ms)
        identity = identity_evidence(route, records)
        output = ""
        envelope: dict[str, Any] = {}
        failure_class: str | None = None
        accepted = False
        if result.returncode != 0:
            failure_class = "transport"
        elif not identity.get("verified"):
            failure_class = "identity"
        else:
            try:
                output, envelope = parse_claude_result(result.stdout)
                accepted = verify_output(output, task["verifier"], workspace)
                failure_class = None if accepted else "gate"
            except RightsizeError:
                failure_class = "task"
        usage = usage_metrics(records)
        return {
            "task_id": task["id"],
            "task_class": task["task_class"],
            "critical": task["critical"],
            "route_id": digest(route),
            "accepted": accepted,
            "failure_class": failure_class,
            "duration_ms": round((ended - started) * 1000),
            "first_output_ms": metric_from_records(records, "firstOutputMs"),
            "tool_steps": envelope.get("tool_steps"),
            "request_injection_evidence": injection,
            "identity_evidence": identity,
            "effort_readback": "unavailable",
            "context_readback": "unavailable",
            "output_sha256": digest_bytes(output.encode("utf-8")) if output else None,
            "usage": usage,
            "cost": attempt_cost(route, records, envelope),
        }
    finally:
        temporary.cleanup()


def wilson_interval(successes: int, attempts: int, z: float) -> tuple[float, float]:
    if attempts == 0:
        return 0.0, 0.0
    proportion = successes / attempts
    denominator = 1 + z * z / attempts
    center = (proportion + z * z / (2 * attempts)) / denominator
    spread = z * math.sqrt(proportion * (1 - proportion) / attempts + z * z / (4 * attempts * attempts)) / denominator
    return max(0.0, center - spread), min(1.0, center + spread)


def mean_available(values: Iterable[int | float | None]) -> float | None:
    present = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.fmean(present) if present else None


def median_available(values: Iterable[int | float | None]) -> float | None:
    present = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.median(present) if present else None


def sum_available(values: Iterable[int | float | None]) -> float | None:
    present = [float(value) for value in values if isinstance(value, (int, float))]
    return sum(present) if present else None


def summarize_route(
    route: dict[str, Any],
    task_class: str,
    attempts: list[dict[str, Any]],
    depth: str,
    pack: dict[str, Any],
    policy: dict[str, Any],
    runtime_admitted: bool,
) -> dict[str, Any]:
    relevant = [attempt for attempt in attempts if attempt["route_id"] == digest(route) and attempt["task_class"] == task_class]
    successes = sum(attempt["accepted"] for attempt in relevant)
    total = len(relevant)
    lower, upper = wilson_interval(successes, total, policy["qualification"]["confidence_z"])
    route_failures = sum(attempt["failure_class"] in {"transport", "identity"} for attempt in relevant)
    critical_failures = sum(attempt["critical"] and not attempt["accepted"] for attempt in relevant)
    distinct_tasks = len({attempt["task_id"] for attempt in relevant})
    costs = [attempt["cost"]["api_equivalent_cost_usd"] for attempt in relevant]
    tokens = [attempt["usage"]["total_tokens"] for attempt in relevant]
    durations = [attempt["duration_ms"] for attempt in relevant]
    qualification = policy["qualification"]
    role_qualified = (
        depth == "qualification"
        and pack["target_representative"]
        and distinct_tasks >= qualification["minimum_distinct_tasks"]
        and total >= distinct_tasks * qualification["minimum_attempts_per_task"]
        and all(
            sum(attempt["task_id"] == task_id for attempt in relevant)
            >= qualification["minimum_attempts_per_task"]
            for task_id in {attempt["task_id"] for attempt in relevant}
        )
        and successes / total >= qualification["minimum_accepted_rate"]
        and lower >= qualification["minimum_wilson_lower_bound"]
        and route_failures <= qualification["maximum_route_or_identity_failures"]
        and critical_failures == 0
        and (
            task_class != "authority_or_frontier"
            or all(attempt["critical"] for attempt in relevant)
        )
    )

    def per_success(values: list[int | float | None]) -> float | None:
        total_value = sum_available(values)
        return None if successes == 0 or total_value is None else total_value / successes

    return {
        "route_id": digest(route),
        "route": route,
        "task_class": task_class,
        "attempts": total,
        "accepted": successes,
        "accepted_rate": successes / total if total else 0.0,
        "wilson_95": {"lower": lower, "upper": upper},
        "transport_or_identity_failure_rate": route_failures / total if total else 0.0,
        "critical_failures": critical_failures,
        "mean_api_equivalent_cost_per_attempt": mean_available(costs),
        "median_api_equivalent_cost_per_attempt": median_available(costs),
        "observed_api_equivalent_cost_per_accepted": per_success(costs),
        "mean_tokens_per_attempt": mean_available(tokens),
        "median_tokens_per_attempt": median_available(tokens),
        "observed_tokens_per_accepted": per_success(tokens),
        "mean_wall_ms_per_attempt": mean_available(durations),
        "median_wall_ms_per_attempt": median_available(durations),
        "observed_wall_ms_per_accepted": per_success(durations),
        "qualification_state": "role-qualified" if role_qualified else "route-probed" if total else "catalog-only",
        "runtime_policy_admitted": runtime_admitted,
        "dispatchable_recommendation": role_qualified and runtime_admitted,
        "provenance": "observed",
    }


def objective_value(summary: dict[str, Any], objective: str) -> float | None:
    if objective == "api-equivalent-cost":
        return summary["observed_api_equivalent_cost_per_accepted"]
    if objective == "tokens-or-quota":
        return summary["observed_tokens_per_accepted"]
    if objective == "wall-time":
        return summary["observed_wall_ms_per_accepted"]
    return None


def dominates(left: dict[str, Any], right: dict[str, Any], objective: str) -> bool:
    left_cost = objective_value(left, objective)
    right_cost = objective_value(right, objective)
    pairs: list[tuple[float, float, bool]] = [
        (left["wilson_95"]["lower"], right["wilson_95"]["lower"], True),
        (
            left["transport_or_identity_failure_rate"],
            right["transport_or_identity_failure_rate"],
            False,
        ),
    ]
    if objective != "reliability":
        if left_cost is None or right_cost is None:
            return False
        pairs.append((left_cost, right_cost, False))
    no_worse = all(a >= b if maximize else a <= b for a, b, maximize in pairs)
    strictly_better = any(a > b if maximize else a < b for a, b, maximize in pairs)
    return no_worse and strictly_better


def pareto_front(summaries: list[dict[str, Any]], objective: str) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in summaries
        if not any(dominates(other, candidate, objective) for other in summaries if other is not candidate)
    ]


def build_evidence(
    plan: dict[str, Any],
    execution: dict[str, Any],
    attempts: list[dict[str, Any]],
    captured_at: str,
) -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    summaries: list[dict[str, Any]] = []
    for route_plan in execution["eligible"]:
        route = route_plan["route"]
        for task_class in plan["run_spec"]["task_classes"]:
            summary = summarize_route(
                route,
                task_class,
                attempts,
                plan["run_spec"]["evaluation_depth"],
                execution["pack"],
                policy,
                route_plan["discovery_state"]["runtime_policy_admitted"],
            )
            if summary["attempts"]:
                summaries.append(summary)
    measured_fronts = {
        task_class: [
            item["route_id"]
            for item in pareto_front(
                [summary for summary in summaries if summary["task_class"] == task_class],
                plan["run_spec"]["pareto_objective"],
            )
        ]
        for task_class in plan["run_spec"]["task_classes"]
    }
    dispatch_fronts = {
        task_class: [
            item["route_id"]
            for item in pareto_front(
                [
                    summary
                    for summary in summaries
                    if summary["task_class"] == task_class and summary["dispatchable_recommendation"]
                ],
                plan["run_spec"]["pareto_objective"],
            )
        ]
        for task_class in plan["run_spec"]["task_classes"]
    }
    route_probes = [
        {
            "route_id": digest(route_plan["route"]),
            "qualification_state": "route-probed"
            if any(
                attempt["route_id"] == digest(route_plan["route"])
                and attempt["accepted"]
                and attempt["failure_class"] is None
                for attempt in attempts
            )
            else "catalog-only",
        }
        for route_plan in execution["eligible"]
    ]
    return {
        "schema_version": policy["evidence_schema_version"],
        "evaluator_version": EVALUATOR_VERSION,
        "evaluator_sha256": plan["authorization"]["evaluator_sha256"],
        "evaluation_policy_sha256": plan["authorization"]["evaluation_policy_sha256"],
        "task_pack_policy_sha256": plan["authorization"]["task_pack_policy_sha256"],
        "runtime_policy_sha256": plan["authorization"]["runtime_policy_sha256"],
        "launcher_sha256": plan["authorization"]["launcher_sha256"],
        "captured_at": captured_at,
        "authorization_digest": plan["authorization_digest"],
        "target_identity_sha256": plan["authorization"]["target_identity_sha256"],
        "catalog_sha256": plan["authorization"]["catalog_sha256"],
        "benchmark_snapshot_sha256": plan["authorization"]["benchmark_snapshot_sha256"],
        "run_spec": plan["run_spec"],
        "task_pack": plan["task_pack"],
        "route_registry": plan["routes"],
        "attempts": attempts,
        "route_probes": route_probes,
        "summaries": summaries,
        "measured_pareto_fronts": measured_fronts,
        "dispatch_pareto_fronts": dispatch_fronts,
        "limitations": [
            "requested effort and context are not effective readback",
            "subscription marginal cost and quota consumption may be unavailable",
            "local qualification is not production dispatch authorization",
            "mined benchmark evidence cannot promote a qualification rung",
        ],
    }


def route_reference(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **summary["route"],
        "route_id": summary["route_id"],
        "qualification_state": summary["qualification_state"],
        "runtime_policy_admitted": summary["runtime_policy_admitted"],
        "dispatchable_recommendation": summary["dispatchable_recommendation"],
    }


def build_map(evidence: dict[str, Any]) -> dict[str, Any]:
    evidence_sha = digest(evidence)
    calibration_id = "|".join(
        [
            "rightsizing-local-eval-2026-08-12",
            evidence["target_identity_sha256"],
            evidence["catalog_sha256"],
            evidence["task_pack"]["task_pack_sha256"],
            evidence["benchmark_snapshot_sha256"],
            evidence_sha,
            EVALUATOR_VERSION,
        ]
    )
    task_map: dict[str, Any] = {}
    for task_class, classification in CLASSIFICATIONS.items():
        summaries = [item for item in evidence["summaries"] if item["task_class"] == task_class]
        measured_ids = evidence.get("measured_pareto_fronts", {}).get(task_class, [])
        dispatch_ids = evidence.get("dispatch_pareto_fronts", {}).get(task_class, [])
        measured = [item for item in summaries if item["route_id"] in measured_ids]
        measured.sort(
            key=lambda item: (
                -item["wilson_95"]["lower"],
                item["observed_api_equivalent_cost_per_accepted"] is None,
                item["observed_api_equivalent_cost_per_accepted"] or math.inf,
                item["route_id"],
            )
        )
        dispatchable = [item for item in measured if item["route_id"] in dispatch_ids]
        candidates = dispatchable or measured
        primary = route_reference(candidates[0]) if candidates else None
        complement = route_reference(candidates[1]) if len(candidates) > 1 else None
        fallback = [route_reference(item) for item in candidates[2:]]
        if dispatchable:
            status = "recommended"
        elif measured:
            status = "blocked-not-role-qualified-or-runtime-admitted"
        else:
            status = "blocked-no-compatible-local-evidence"
        task_map[task_class] = {
            "classification": classification,
            "primary": primary,
            "complement": complement,
            "fallback": fallback,
            "measured_pareto_front": measured_ids,
            "dispatch_pareto_front": dispatch_ids,
            "gate": classification["determinism_of_gate"],
            "kill_criteria": "stop on route/identity failure, missing control, budget exhaustion, or unresolved context",
            "status": status,
        }
    return {
        "schema_version": "model-task-map/v2",
        "calibration_id": calibration_id,
        "generated_from_evidence_sha256": evidence_sha,
        "run_spec": evidence["run_spec"],
        "route_registry": evidence["route_registry"],
        "map": task_map,
        "authority_boundary": "recommendation only; not a dispatch receipt or authorization",
    }


def with_payload_digest(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result["generated_content_sha256"] = digest(value)
    return result


def markdown_for(model_map: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = [
        "# Model-task map v2",
        "",
        f"Calibration: `{model_map['calibration_id']}`",
        f"Evidence: `{model_map['generated_from_evidence_sha256']}`",
        "",
        "> Recommendation only. This is not a dispatch receipt or authorization.",
        "",
        "## Probe and evaluation",
        "",
        f"- Captured: `{evidence['captured_at']}`",
        f"- Task pack: `{evidence['task_pack']['id']}` (`{evidence['task_pack']['task_pack_sha256']}`)",
        f"- Evaluation depth: `{evidence['run_spec']['evaluation_depth']}`",
        f"- Pareto objective: `{evidence['run_spec']['pareto_objective']}`",
        "- Effective effort/context readback: unavailable unless independently reported",
        "",
        "## Recommendations",
        "",
        "| Task class | Primary | State | Runtime policy | Complement |",
        "|---|---|---|---|---|",
    ]
    for task_class, entry in model_map["map"].items():
        primary = entry["primary"]
        complement = entry["complement"]
        if primary is None:
            lines.append(f"| `{task_class}` | blocked | — | — | — |")
            continue
        suffix = primary["requested_context_form"] if primary["requested_context_form"] == "[1m]" else ""
        primary_label = f"`{primary['requested_model_id']}{suffix}` `{primary['requested_effort']}`"
        complement_label = "—"
        if complement is not None:
            complement_suffix = complement["requested_context_form"] if complement["requested_context_form"] == "[1m]" else ""
            complement_label = f"`{complement['requested_model_id']}{complement_suffix}`"
        lines.append(
            f"| `{task_class}` | {primary_label} | `{primary['qualification_state']}` | "
            f"`{'admitted' if primary['runtime_policy_admitted'] else 'blocked'}` | {complement_label} |"
        )
    lines.extend(
        [
            "",
            "## Unavailable or blocked evidence",
            "",
        ]
    )
    blocked = [route for route in evidence["route_registry"] if route["blockers"]]
    if blocked:
        for route in blocked:
            lines.append(
                f"- `{route['route']['requested_model_id']}`: {', '.join(route['blockers'])}"
            )
    else:
        lines.append("- None at planning time.")
    lines.extend(
        [
            "",
            "## Regeneration",
            "",
            "```text",
            f"mise run rightsize:evaluate -- render --evidence {Path(evidence['run_spec']['output']).with_suffix('.evidence.json').name}",
            "```",
            "",
            "Policy: [`model-tier-rightsizing`](../skills/model-tier-rightsizing/SKILL.md) · "
            "[calibration](../skills/model-tier-rightsizing/references/model-routing-calibration.md)",
            "",
        ]
    )
    return "\n".join(lines)


def artifact_paths(target_root: Path, output: str) -> tuple[Path, Path, Path]:
    path = Path(output).expanduser()
    if not path.is_absolute():
        path = target_root / path
    path = path.resolve()
    try:
        path.relative_to(target_root.resolve())
    except ValueError as exc:
        raise RightsizeError("output-outside-target") from exc
    if path.suffix != ".json":
        raise RightsizeError("output-must-be-json")
    return path, path.with_suffix(".md"), path.with_suffix(".evidence.json")


def read_valid_json_artifact(path: Path, schema_version: str | None = None) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except RightsizeError:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("generated_content_sha256"), str):
        return None
    stated = value.pop("generated_content_sha256")
    if digest(value) != stated or (schema_version is not None and value.get("schema_version") != schema_version):
        return None
    return value


def valid_json_artifact(path: Path) -> bool:
    return read_valid_json_artifact(path) is not None


def valid_markdown_artifact(path: Path, model_map: dict[str, Any], evidence: dict[str, Any]) -> bool:
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError:
        return False
    marker, separator, body = contents.partition("\n")
    prefix = "<!-- generated-content-sha256:"
    if not separator or not marker.startswith(prefix) or not marker.endswith(" -->"):
        return False
    stated = marker[len(prefix) : -4]
    return (
        len(stated) == 64
        and all(character in "0123456789abcdef" for character in stated)
        and digest_bytes(body.encode("utf-8")) == stated
        and body == markdown_for(model_map, evidence)
    )


def check_replacement(paths: tuple[Path, Path, Path], spec: dict[str, Any]) -> None:
    exists = [path.exists() for path in paths]
    if not any(exists):
        return
    if not all(exists):
        if not (spec["regenerate"] and spec["force"]):
            raise RightsizeError("partial-output-requires-regenerate-force")
        return
    if not spec["regenerate"]:
        raise RightsizeError("output-exists-requires-regenerate")
    model_map = read_valid_json_artifact(paths[0], "model-task-map/v2")
    evidence = read_valid_json_artifact(paths[2], "rightsize-evidence/v1")
    trio_valid = (
        model_map is not None
        and evidence is not None
        and model_map.get("generated_from_evidence_sha256") == digest(evidence)
        and valid_markdown_artifact(paths[1], model_map, evidence)
    )
    if not trio_valid and not spec["force"]:
        raise RightsizeError("edited-output-requires-force")


def validate_evidence(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict) or evidence.get("schema_version") != "rightsize-evidence/v1":
        raise RightsizeError("unsupported-evidence-version")
    expected_digests = {
        "evaluator_sha256": EVALUATOR_PATH,
        "evaluation_policy_sha256": POLICY_PATH,
        "task_pack_policy_sha256": TASK_POLICY_PATH,
        "runtime_policy_sha256": RUNTIME_POLICY_PATH,
        "launcher_sha256": LAUNCHER_PATH,
    }
    for field, path in expected_digests.items():
        value = evidence.get(field)
        if not isinstance(value, str):
            raise RightsizeError(f"incompatible-evidence:{field}")
        if digest_bytes(path.read_bytes()) != value:
            raise RightsizeError(f"stale-evidence:{field}")
    for field in (
        "authorization_digest",
        "target_identity_sha256",
        "catalog_sha256",
        "benchmark_snapshot_sha256",
    ):
        if not isinstance(evidence.get(field), str):
            raise RightsizeError(f"invalid-evidence:{field}")
    run_spec = evidence.get("run_spec")
    if not isinstance(run_spec, dict):
        raise RightsizeError("invalid-evidence:run_spec")
    validate_spec(run_spec, load_json(POLICY_PATH))
    if not isinstance(evidence.get("route_registry"), list):
        raise RightsizeError("invalid-evidence:route_registry")
    if not isinstance(evidence.get("attempts"), list) or not isinstance(evidence.get("summaries"), list):
        raise RightsizeError("invalid-evidence:measurements")
    return evidence


def render_bundle(evidence: dict[str, Any], target_root: Path, *, write: bool) -> dict[str, Any]:
    evidence = validate_evidence(evidence)
    model_map = build_map(evidence)
    map_artifact = with_payload_digest(model_map)
    evidence_artifact = with_payload_digest(evidence)
    markdown_body = markdown_for(model_map, evidence)
    markdown_digest = digest_bytes(markdown_body.encode("utf-8"))
    markdown = f"<!-- generated-content-sha256:{markdown_digest} -->\n{markdown_body}"
    paths = artifact_paths(target_root, evidence["run_spec"]["output"])
    if write:
        check_replacement(paths, evidence["run_spec"])
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        payloads = [pretty_json(map_artifact), markdown, pretty_json(evidence_artifact)]
        staged: list[Path] = []
        try:
            for path, payload in zip(paths, payloads, strict=True):
                temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
                temporary.write_text(payload, encoding="utf-8")
                staged.append(temporary)
            for temporary, path in zip(staged, paths, strict=True):
                os.replace(temporary, path)
        finally:
            for temporary in staged:
                temporary.unlink(missing_ok=True)
    return {
        "map": map_artifact,
        "markdown": markdown,
        "evidence": evidence_artifact,
        "paths": [path.name for path in paths],
        "written": write,
    }


def evaluate_run(
    plan: dict[str, Any],
    execution: dict[str, Any],
    target_root: Path,
    *,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    started = time.monotonic()
    total_cost = 0.0
    budgets = plan["run_spec"]["budgets"]
    per_call_budget = budgets["max_api_equivalent_usd"] / plan["authorization"]["exact_model_calls"]
    for route_plan in execution["eligible"]:
        for task in execution["tasks"]:
            for _ in range(plan["authorization"]["attempts_per_task"]):
                remaining_seconds = budgets["max_wall_seconds"] - (time.monotonic() - started)
                if remaining_seconds <= 0:
                    raise RightsizeError("wall-time-budget-exhausted")
                if "fixture" in task:
                    source = (execution["pack_path"].parent / task["fixture"]).resolve()
                    if fixture_digest(source) != task["fixture_sha256"]:
                        raise RightsizeError(f"fixture-changed-after-authorization:{task['id']}")
                attempt = run_attempt(
                    route_plan["route"],
                    task,
                    execution["pack_path"],
                    per_call_budget,
                    max(1, math.ceil(remaining_seconds)),
                    runner=runner,
                )
                attempts.append(attempt)
                cost = attempt["cost"]["api_equivalent_cost_usd"]
                if isinstance(cost, (int, float)):
                    total_cost += cost
                if total_cost > budgets["max_api_equivalent_usd"]:
                    raise RightsizeError("api-equivalent-cost-budget-exhausted")
                if attempt["failure_class"] in {"transport", "identity"}:
                    raise RightsizeError(f"attempt-failed-closed:{attempt['failure_class']}")
    evidence = build_evidence(plan, execution, attempts, utc_timestamp())
    return render_bundle(evidence, target_root, write=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    discover_parser = subparsers.add_parser("discover", help="Inspect route candidates without model calls")
    discover_parser.add_argument("--target", default=".")
    plan_parser = subparsers.add_parser("plan", help="Normalize and preview an evaluation")
    plan_parser.add_argument("--target", default=".")
    plan_parser.add_argument("--spec", required=True)
    evaluate_parser = subparsers.add_parser("evaluate", help="Run one authorization-digest-bound evaluation")
    evaluate_parser.add_argument("--target", default=".")
    evaluate_parser.add_argument("--spec", required=True)
    evaluate_parser.add_argument("--authorization-digest", required=True)
    render_parser = subparsers.add_parser("render", help="Render an existing closed evidence artifact")
    render_parser.add_argument("--target", default=".")
    render_parser.add_argument("--evidence", required=True)
    render_parser.add_argument("--write", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        target_root, _ = repository_identity(Path(args.target))
        if args.command == "discover":
            print(pretty_json(discover(Path(args.target))), end="")
            return 0
        if args.command == "render":
            evidence = load_json(Path(args.evidence))
            if isinstance(evidence, dict) and "generated_content_sha256" in evidence:
                evidence = copy.deepcopy(evidence)
                stated = evidence.pop("generated_content_sha256")
                if digest(evidence) != stated:
                    raise RightsizeError("evidence-generated-digest-mismatch")
            print(pretty_json(render_bundle(evidence, target_root, write=args.write)), end="")
            return 0
        discovery = discover(Path(args.target))
        plan, execution = plan_run(load_spec(args.spec), discovery, target_root)
        if args.command == "plan":
            print(pretty_json(plan), end="")
            return 0
        if args.authorization_digest != plan["authorization_digest"]:
            raise RightsizeError("authorization-digest-mismatch")
        print(pretty_json(evaluate_run(plan, execution, target_root)), end="")
        return 0
    except (OSError, RightsizeError) as exc:
        message = exc.args[0] if exc.args else type(exc).__name__
        print(pretty_json({"status": "refused", "reason": str(message)}), end="", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
