#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Own the durable RouteQualification layer for exact route/class cells.

Five verbs, all pure over documents supplied on the command line: `issue` turns one recorded
`rightsize-evidence/v1` artifact into one immutable qualification generation, `validate` checks a
store, `admit` derives the pre-dispatch verdict a conductor needs before writing a resolved
`RuntimeAssignment`, and `quarantine`/`recover` transform a store through the one lifecycle that
takes a cell out of service and the one that brings it back.

Nothing here reaches a network, a subprocess, a gateway, a catalog, a credential, or a model, and
no verb writes a file: a transform prints the new document and the caller decides whether to
persist it. That is deliberate. Qualification is one layer among several (product-spec Decision
50), so this surface must not be able to probe a route, refresh a credential, or dispatch, and an
admitted cell is evidence rather than authorization.

The promotion floor itself is NOT implemented here. It is imported from `rightsize.py`, the one
rightsizing evaluator Decision 49 delegates qualification to.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = SKILL_ROOT / "policy" / "route-qualification-v1.json"
EVALUATION_POLICY_PATH = SKILL_ROOT / "policy" / "rightsize-evaluation-v1.json"
EVALUATOR_PATH = Path(__file__).resolve().parent / "rightsize.py"
EVIDENCE_SCHEMA = "rightsize-evidence/v1"
GATEWAY_ROUTED = "gateway-routed-provider"
#: What the gateway's attribution names as the provider on the Claude-subscription passthrough
#: route. The passthrough is not an OCX catalog row, so its attribution reports this fixed
#: upstream rather than the route's own `provider` field, and re-deriving identity for that route
#: kind means comparing against this value.
PASSTHROUGH_ATTRIBUTION_PROVIDER = "anthropic-native"

#: A verdict was derived. Refusing dispatch is this command SUCCEEDING at deriving one.
EXIT_OK = 0
#: An unexpected internal failure, including a stdout that cannot receive the result document.
EXIT_INTERNAL = 1
#: A supplied document is unreadable, not JSON, not what it claims to be, or the arguments are
#: unusable. Issuance refusals land here too: an evidence document that cannot support any verdict
#: is an unusable input, not a cell that measured badly.
EXIT_INPUT = 2


class InputError(Exception):
    """A named refusal of a supplied document or argument."""


def load_evaluator() -> Any:
    """Load `rightsize.py` as a module so the floor has exactly one implementation.

    It is loaded by path rather than imported by name because it is a `uv` single-file script
    living in a directory that is not a package. Only the pure floor helpers are used; nothing
    that runs an evaluation is reachable from here.
    """
    spec = importlib.util.spec_from_file_location("rightsize", EVALUATOR_PATH)
    if spec is None or spec.loader is None:
        raise InputError(f"the rightsizing evaluator at {EVALUATOR_PATH.name} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_no_duplicate_members(raw: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON member: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=reject_duplicates)


def load_document(path: str, label: str) -> dict[str, Any]:
    try:
        parsed = parse_no_duplicate_members(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"the {label} at {path} could not be read: {exc.strerror}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise InputError(f"the {label} at {path} is not usable JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InputError(f"the {label} at {path} must be one JSON object")
    return parsed


def load_policy() -> dict[str, Any]:
    policy = load_document(str(POLICY_PATH), "route qualification policy")
    if policy.get("schema_version") != policy.get("policy_schema_version"):
        raise InputError("the route qualification policy does not agree with its own schema version")
    return policy


def floor_policy_digest() -> str:
    """Digest the floor block alone, so a threshold change invalidates stored generations.

    Bound to the `qualification` block rather than the whole evaluation policy on purpose: a
    budget-limit edit must not expire every qualification in the store, while a change to the
    distinct-task count, the accepted rate, or the Wilson bound must, because a generation issued
    under the old floor was never measured against the new one.
    """
    evaluation_policy = load_document(str(EVALUATION_POLICY_PATH), "rightsize evaluation policy")
    qualification = evaluation_policy.get("qualification")
    if not isinstance(qualification, dict):
        raise InputError("the rightsize evaluation policy carries no qualification floor block")
    return sha256_json(qualification)


def parse_timestamp(value: Any, label: str, policy: dict[str, Any]) -> datetime:
    """Admit exactly one timestamp spelling, because a second one is a second clock.

    An offset form, a fractional second, or a bare date would each have to be normalized before it
    could be compared, and a normalization this surface performs silently is a freshness decision
    made where nobody can see it. The refusal names the format instead.
    """
    if not isinstance(value, str):
        raise InputError(f"{label} must be a {policy['timestamp_format']} timestamp string")
    try:
        return datetime.strptime(value, policy["timestamp_format"]).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise InputError(f"{label} is not a {policy['timestamp_format']} timestamp: {value}") from exc


def format_timestamp(value: datetime, policy: dict[str, Any]) -> str:
    return value.strftime(policy["timestamp_format"])


def exact_object(value: Any, fields: list[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"the {label} must be a JSON object")
    missing = sorted(set(fields) - set(value))
    unexpected = sorted(set(value) - set(fields))
    if missing:
        raise InputError(f"the {label} is missing fields: {', '.join(missing)}")
    if unexpected:
        raise InputError(f"the {label} carries unexpected fields: {', '.join(unexpected)}")
    return value


def route_identity_matches(route: dict[str, Any], provider: Any, model_id: Any) -> bool:
    """Compare an observed provider/model pair against the route it is claimed to belong to.

    The model comparison drops a namespace prefix because the gateway's attribution record names
    the upstream's own bare ID while the route requests the namespaced form (`muse/muse-spark-1.2`
    resolves as `muse-spark-1.2`). The provider comparison is exact: the prefix is exactly the fact
    a default-provider fallthrough gets wrong, so accepting a near miss there would accept the
    misroute this refusal exists to catch.
    """
    expected_model = str(route["requested_model_id"]).split("/", 1)[-1]
    observed_model = str(model_id).split("/", 1)[-1] if isinstance(model_id, str) else None
    return provider == route["provider"] and observed_model == expected_model


# ---------------------------------------------------------------------------- issue


def select_route(evidence: dict[str, Any], route_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Take the exact route from the evidence's own registry, never from an argument.

    The caller names a `route_id` and gets the tuple the evaluation actually measured. A
    caller-supplied tuple could describe a different provider, effort, or context form than the
    attempts were run against, and the resulting generation would qualify a route nothing measured.
    """
    registry = evidence.get("route_registry")
    if not isinstance(registry, list):
        raise InputError(f"the {EVIDENCE_SCHEMA} document carries no route_registry list")
    matches = []
    for entry in registry:
        if not isinstance(entry, dict) or not isinstance(entry.get("route"), dict):
            continue
        route = exact_object(entry["route"], policy["canonical_route_fields"], "route registry tuple")
        if sha256_json(route) == route_id:
            matches.append(route)
    if not matches:
        raise InputError(f"no route in the evidence registry digests to route_id {route_id}")
    if len({canonical_json(route) for route in matches}) > 1:
        raise InputError(f"route_id {route_id} names more than one distinct route tuple in the registry")
    route = matches[0]
    # An unrecognized route kind must refuse rather than fall through to the passthrough identity
    # rule, which would apply the wrong expected provider to a route nobody has characterized.
    route_kinds = load_document(str(EVALUATION_POLICY_PATH), "rightsize evaluation policy")["route_kinds"]
    if route["route_kind"] not in route_kinds:
        raise InputError(
            f"route_kind {route['route_kind']!r} is not one of {', '.join(route_kinds)}, so its "
            "identity rule is uncharacterized and it cannot be qualified"
        )
    return route


def attempt_identity_errors(route: dict[str, Any], relevant: list[dict[str, Any]]) -> list[str]:
    """Re-derive identity correlation from each attempt's own recorded excerpts.

    The attempt records carry a `verified` flag that the capture path set, and trusting that flag
    alone would let a hand-assembled evidence document assert correlation it does not have. So the
    provider and resolved model in every excerpt are compared against the route being qualified,
    and a `default-provider` route decision is refused by name — that is the router forwarding an
    unrecognized model string to whichever provider is default, which bills the wrong upstream
    while attribution records the selected provider rather than the requested one.
    """
    errors: list[str] = []
    for index, attempt in enumerate(relevant):
        identity = attempt.get("identity_evidence")
        if not isinstance(identity, dict):
            errors.append(f"attempt {index} carries no identity_evidence object")
            continue
        if identity.get("verified") is not True:
            errors.append(f"attempt {index} identity_evidence is not verified: {identity.get('failure')}")
            continue
        records = identity.get("records")
        if not isinstance(records, list) or not records:
            errors.append(f"attempt {index} identity_evidence carries no correlated attribution records")
            continue
        for record in records:
            if not isinstance(record, dict):
                errors.append(f"attempt {index} attribution record is not an object")
                continue
            if record.get("route_kind") == "default-provider":
                errors.append(f"attempt {index} attribution records a default-provider fallthrough")
                continue
            if route["route_kind"] == GATEWAY_ROUTED:
                if not route_identity_matches(route, record.get("provider"), record.get("resolved_model")):
                    errors.append(
                        f"attempt {index} attribution names provider {record.get('provider')!r} and model "
                        f"{record.get('resolved_model')!r}, which is not the route being qualified"
                    )
            elif record.get("provider") != PASSTHROUGH_ATTRIBUTION_PROVIDER:
                # Skipping this branch would leave a passthrough qualification resting on the
                # recorded `verified` flag alone, which is the one thing re-derivation exists not to
                # trust.
                errors.append(
                    f"attempt {index} attribution names provider {record.get('provider')!r} on a "
                    f"{route['route_kind']} route, which expects {PASSTHROUGH_ATTRIBUTION_PROVIDER}"
                )
    return errors


def issue_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    policy = load_policy()
    evaluator = load_evaluator()
    evidence = load_document(args.evidence, "rightsize evidence document")
    if evidence.get("schema_version") != EVIDENCE_SCHEMA:
        raise InputError(
            f"qualification is issued only from a {EVIDENCE_SCHEMA} document of locally observed "
            f"attempts; {args.evidence} declares {evidence.get('schema_version')!r}"
        )
    if args.task_class not in policy["task_classes"]:
        raise InputError(f"{args.task_class} is not one of the eight task classes")

    route = select_route(evidence, args.route_id, policy)
    attempts = evidence.get("attempts")
    if not isinstance(attempts, list):
        raise InputError(f"the {EVIDENCE_SCHEMA} document carries no attempts list")
    relevant = [
        attempt
        for attempt in attempts
        if isinstance(attempt, dict)
        and attempt.get("route_id") == args.route_id
        and attempt.get("task_class") == args.task_class
    ]
    if not relevant:
        raise InputError(
            f"the evidence records no attempt for route {args.route_id} in class {args.task_class}, "
            "so there is nothing to reach a verdict over"
        )

    # Mined or declared evidence cannot issue at all, and refusing is more honest than recording an
    # `unqualified` generation: an unqualified verdict asserts this route was measured and fell
    # short, while mined evidence never measured this route.
    admissible = policy["evidence_provenance_admissible_for_issue"]
    inadmissible = sorted(
        {
            summary.get("provenance")
            for summary in evidence.get("summaries", [])
            if isinstance(summary, dict)
            and summary.get("route_id") == args.route_id
            and summary.get("task_class") == args.task_class
        }
        - set(admissible),
        key=str,
    )
    if inadmissible:
        raise InputError(
            f"evidence provenance {inadmissible[0]!r} cannot issue a qualification; only "
            f"{', '.join(admissible)} evidence may, so a mined or declared result nominates a "
            "candidate rather than promoting one"
        )

    identity_errors = attempt_identity_errors(route, relevant)
    if identity_errors:
        raise InputError(
            "the recorded attempts do not correlate to the route being qualified: "
            + "; ".join(identity_errors)
        )

    run_spec = evidence.get("run_spec") if isinstance(evidence.get("run_spec"), dict) else {}
    pack = evidence.get("task_pack") if isinstance(evidence.get("task_pack"), dict) else {}
    floor = evaluator.qualification_floor(
        relevant,
        args.task_class,
        run_spec.get("evaluation_depth"),
        bool(pack.get("target_representative")),
        load_document(str(EVALUATION_POLICY_PATH), "rightsize evaluation policy"),
    )

    issued_at = parse_timestamp(args.issued_at, "--issued-at", policy)
    horizon = timedelta(days=policy["freshness"]["route_class_qualification_max_age_days"])
    generation = {
        "schema_version": policy["verdict_schema_versions"]["generation"],
        "generation_id": "",
        "route": route,
        "route_id": args.route_id,
        "task_class": args.task_class,
        "verdict": "qualified" if floor["met"] else "unqualified",
        "evidence_provenance": "observed",
        "evidence_digest_sha256": sha256_json(relevant),
        "evidence_captured_at": format_timestamp(
            parse_timestamp(evidence.get("captured_at"), "the evidence captured_at", policy), policy
        ),
        "evidence_evaluation_policy_sha256": evidence.get("evaluation_policy_sha256"),
        "evaluator_version": evaluator.EVALUATOR_VERSION,
        "floor_policy_sha256": floor_policy_digest(),
        "issued_at": format_timestamp(issued_at, policy),
        "expires_at": format_timestamp(issued_at + horizon, policy),
        "measured": floor["measured"],
        "unmet_requirements": floor["unmet_requirements"],
        "authority_boundary": policy["authority_boundary"],
    }
    return finalize_generation(generation, policy), EXIT_OK


def finalize_generation(generation: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Seal a generation by naming it after its own content.

    `generation_id` is the digest of everything else, so an edited generation stops naming itself
    and `validate` reports it. Field order follows the policy's canonical list so two runs over the
    same evidence produce byte-identical output.
    """
    body = {key: value for key, value in generation.items() if key != "generation_id"}
    generation["generation_id"] = sha256_json(body)
    return {field: generation[field] for field in policy["canonical_generation_fields"]}


# ---------------------------------------------------------------------------- validate


def store_errors(store: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """Report every structural fault in a store rather than the first.

    Duplicate generation IDs and self-digest mismatches are the two faults that would otherwise
    let a store silently carry a second, edited history of the same cell.
    """
    errors: list[str] = []
    if store.get("schema_version") != policy["verdict_schema_versions"]["store"]:
        errors.append(
            f"store schema_version must be {policy['verdict_schema_versions']['store']}, "
            f"found {store.get('schema_version')!r}"
        )
    for field in policy["canonical_store_fields"]:
        if field == "schema_version":
            continue
        if not isinstance(store.get(field), list):
            errors.append(f"store {field} must be a list")
    unexpected = sorted(set(store) - set(policy["canonical_store_fields"]))
    if unexpected:
        errors.append(f"store carries unexpected fields: {', '.join(unexpected)}")
    if errors:
        return errors

    seen: set[str] = set()
    for index, generation in enumerate(store["generations"]):
        try:
            exact_object(generation, policy["canonical_generation_fields"], f"generation {index}")
        except InputError as exc:
            errors.append(str(exc))
            continue
        if generation["schema_version"] != policy["verdict_schema_versions"]["generation"]:
            errors.append(f"generation {index} declares an unsupported schema_version")
        if generation["verdict"] not in policy["verdicts"]:
            errors.append(f"generation {index} verdict {generation['verdict']!r} is not an allowed verdict")
        if generation["task_class"] not in policy["task_classes"]:
            errors.append(f"generation {index} task_class {generation['task_class']!r} is not a task class")
        body = {key: value for key, value in generation.items() if key != "generation_id"}
        if sha256_json(body) != generation["generation_id"]:
            errors.append(f"generation {index} generation_id does not digest its own content")
        if generation["generation_id"] in seen:
            errors.append(f"generation {index} repeats generation_id {generation['generation_id']}")
        seen.add(generation["generation_id"])
        if not isinstance(generation["route"], dict) or sha256_json(generation["route"]) != generation["route_id"]:
            errors.append(f"generation {index} route_id does not digest its own route tuple")
        # A qualified verdict with unmet requirements, or an unqualified one with none, would make
        # the record disagree with itself about the floor it recorded.
        if bool(generation["unmet_requirements"]) == (generation["verdict"] == "qualified"):
            errors.append(f"generation {index} verdict contradicts its own unmet_requirements")

    for index, quarantine in enumerate(store["quarantines"]):
        try:
            exact_object(quarantine, policy["canonical_quarantine_fields"], f"quarantine {index}")
        except InputError as exc:
            errors.append(str(exc))
            continue
        if quarantine["cause"] not in policy["quarantine_causes"]:
            errors.append(f"quarantine {index} cause {quarantine['cause']!r} is not an allowed cause")
    for index, recovery in enumerate(store["recoveries"]):
        try:
            exact_object(recovery, policy["canonical_recovery_fields"], f"recovery {index}")
        except InputError as exc:
            errors.append(str(exc))
    return errors


def load_store(path: str, policy: dict[str, Any]) -> dict[str, Any]:
    store = load_document(path, "route qualification store")
    errors = store_errors(store, policy)
    if errors:
        raise InputError("the route qualification store is not usable: " + "; ".join(errors))
    return store


def validate_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    policy = load_policy()
    store = load_document(args.store, "route qualification store")
    errors = store_errors(store, policy)
    result = {
        "schema_version": policy["verdict_schema_versions"]["store"],
        "command": "validate",
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "cells": sorted(
            {
                f"{generation.get('route_id')}:{generation.get('task_class')}"
                for generation in store.get("generations", [])
                if isinstance(generation, dict)
            }
        )
        if not errors
        else [],
    }
    return result, EXIT_OK


# ---------------------------------------------------------------------------- admit


def cell_generations(store: dict[str, Any], route_id: str, task_class: str) -> list[dict[str, Any]]:
    return [
        generation
        for generation in store["generations"]
        if generation["route_id"] == route_id and generation["task_class"] == task_class
    ]


def active_quarantine(
    store: dict[str, Any], route_id: str, task_class: str
) -> dict[str, Any] | None:
    """The oldest quarantine for this exact cell that no recovery resolves.

    Scoped to one `route_id` and one `task_class` because story 67 quarantines the exact cell:
    another class on the same route, and another route in the same class, stay admissible.
    """
    recovered = {
        recovery["resolves_quarantined_at"]
        for recovery in store["recoveries"]
        if recovery["route_id"] == route_id and recovery["task_class"] == task_class
    }
    open_entries = [
        quarantine
        for quarantine in store["quarantines"]
        if quarantine["route_id"] == route_id
        and quarantine["task_class"] == task_class
        and quarantine["quarantined_at"] not in recovered
    ]
    return min(open_entries, key=lambda entry: entry["quarantined_at"]) if open_entries else None


class Ambiguous(Exception):
    """Two distinct generations share the newest issue instant for one cell."""


def select_current_generation(generations: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the one current generation, or refuse because there is no single one.

    Decision 40 requires selecting a COMPLETE current generation atomically. Two generations
    issued at the same instant for the same cell give no basis for preferring either, and picking
    by list order would make the answer depend on how the file was assembled, so the ambiguity is
    reported instead of resolved. The timestamps compare as strings because the one admitted
    spelling is fixed-width and zero-padded, which makes lexical and chronological order the same.
    """
    latest = max(generations, key=lambda generation: generation["issued_at"])
    tied = [generation for generation in generations if generation["issued_at"] == latest["issued_at"]]
    if len({generation["generation_id"] for generation in tied}) > 1:
        raise Ambiguous(latest["issued_at"])
    return latest


def refusal(
    policy: dict[str, Any],
    route_id: str,
    task_class: str,
    reason: str,
    detail: str,
    *,
    generation_id: str | None = None,
    quarantine_cause: str | None = None,
) -> dict[str, Any]:
    if reason not in policy["refusal_reasons"]:
        raise InputError(f"{reason} is not a declared refusal reason")
    return {
        "schema_version": policy["verdict_schema_versions"]["admission"],
        "command": "admit",
        "verdict": "refuse-dispatch",
        "route_id": route_id,
        "task_class": task_class,
        "reason": reason,
        "detail": detail,
        "quarantine_required": quarantine_cause is not None,
        "quarantine_cause": quarantine_cause,
        "selected_generation_id": generation_id,
        "expires_at": None,
        "authority_boundary": policy["authority_boundary"],
    }


def admit_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    policy = load_policy()
    store = load_store(args.store, policy)
    if args.task_class not in policy["task_classes"]:
        raise InputError(f"{args.task_class} is not one of the eight task classes")
    at = parse_timestamp(args.at, "--at", policy)
    route_id = args.route_id

    def say(reason: str, detail: str, **extra: Any) -> dict[str, Any]:
        return refusal(policy, route_id, args.task_class, reason, detail, **extra)

    quarantine = active_quarantine(store, route_id, args.task_class)
    if quarantine is not None:
        return (
            say(
                "cell-quarantined",
                f"this exact route/class cell was quarantined at {quarantine['quarantined_at']} for "
                f"{quarantine['cause']} and no recovery resolves it; re-qualify the cell and record a "
                "recovery, because no probe, configuration change, or credential refresh clears a "
                "quarantine",
            ),
            EXIT_OK,
        )

    generations = cell_generations(store, route_id, args.task_class)
    if not generations:
        return (
            say(
                "no-generation-for-cell",
                f"the store records no qualification generation for route {route_id} in class "
                f"{args.task_class}; an unmeasured cell is not a failed one, and it is not "
                "dispatchable either",
            ),
            EXIT_OK,
        )
    try:
        current = select_current_generation(generations)
    except Ambiguous as exc:
        return (
            say(
                "ambiguous-current-generation",
                f"two distinct generations for this cell share the newest issued_at {exc.args[0]}, so "
                "no single current generation can be selected; remove the one that should not have "
                "been recorded rather than letting file order decide",
            ),
            EXIT_OK,
        )

    generation_id = current["generation_id"]
    if current["verdict"] != "qualified":
        return (
            say(
                "generation-unqualified",
                "the current generation for this cell recorded an unqualified verdict, missing: "
                + ", ".join(current["unmet_requirements"]),
                generation_id=generation_id,
            ),
            EXIT_OK,
        )
    if at > parse_timestamp(current["expires_at"], "the generation expires_at", policy):
        return (
            say(
                "qualification-expired",
                f"the current generation expired at {current['expires_at']} and the query is at "
                f"{args.at}; qualification is current for at most "
                f"{policy['freshness']['route_class_qualification_max_age_days']} days and only a "
                "qualification refresh renews it",
                generation_id=generation_id,
            ),
            EXIT_OK,
        )
    if current["floor_policy_sha256"] != floor_policy_digest():
        return (
            say(
                "floor-policy-drift",
                "the promotion floor changed since this generation was issued, so the cell was never "
                "measured against the floor in force now; re-qualify it",
                generation_id=generation_id,
            ),
            EXIT_OK,
        )

    identity_refusal = admit_identity(args, current, policy, say)
    if identity_refusal is not None:
        return identity_refusal, EXIT_OK

    return (
        {
            "schema_version": policy["verdict_schema_versions"]["admission"],
            "command": "admit",
            "verdict": "admit-dispatch",
            "route_id": route_id,
            "task_class": args.task_class,
            "reason": None,
            "detail": (
                "this exact route/class cell holds a current qualified generation and the presented "
                "identity correlates to it; request injection, runtime-receipt admission, and host "
                "identity readback remain separate and unproven here"
            ),
            "quarantine_required": False,
            "quarantine_cause": None,
            "selected_generation_id": generation_id,
            "expires_at": current["expires_at"],
            "authority_boundary": policy["authority_boundary"],
        },
        EXIT_OK,
    )


def admit_identity(
    args: argparse.Namespace,
    current: dict[str, Any],
    policy: dict[str, Any],
    say: Any,
) -> dict[str, Any] | None:
    """Check the identity the conductor holds against the qualified route.

    An identity mismatch and a default-provider fallthrough are quarantine events (Decisions 51 and
    67), so the refusal names the cause the caller must record. It is NAMED rather than applied:
    this verb transforms no store, which keeps the read-only admission query from silently mutating
    durable state on the strength of one caller-supplied document.
    """
    if args.observed_provider is None and args.observed_model_id is None:
        return say(
            "identity-evidence-missing",
            "no observed provider/model was presented, so nothing correlates the qualified route to "
            "what the transport would actually serve; a qualified cell is not identity evidence",
            generation_id=current["generation_id"],
        )
    if args.observed_route_kind == "default-provider":
        return say(
            "default-provider-fallthrough",
            "the presented route decision is default-provider, which means the router did not "
            "recognize the target and forwarded it to whichever provider is default; that is a "
            "quarantine event, not a route",
            generation_id=current["generation_id"],
            quarantine_cause="default-provider-fallthrough",
        )
    if not route_identity_matches(current["route"], args.observed_provider, args.observed_model_id):
        return say(
            "route-identity-uncorrelated",
            f"the presented identity {args.observed_provider!r}/{args.observed_model_id!r} is not the "
            f"qualified route {current['route']['provider']!r}/"
            f"{current['route']['requested_model_id']!r}; a material identity change invalidates "
            "qualification immediately",
            generation_id=current["generation_id"],
            quarantine_cause="identity-mismatch",
        )
    return None


# ------------------------------------------------------------------- quarantine / recover


def quarantine_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    policy = load_policy()
    store = load_store(args.store, policy)
    if args.task_class not in policy["task_classes"]:
        raise InputError(f"{args.task_class} is not one of the eight task classes")
    if args.cause not in policy["quarantine_causes"]:
        raise InputError(
            f"{args.cause} is not a quarantine cause; the closed set is "
            f"{', '.join(policy['quarantine_causes'])}"
        )
    quarantined_at = format_timestamp(parse_timestamp(args.at, "--at", policy), policy)
    if any(
        entry["route_id"] == args.route_id
        and entry["task_class"] == args.task_class
        and entry["quarantined_at"] == quarantined_at
        for entry in store["quarantines"]
    ):
        raise InputError(
            f"a quarantine for this cell at {quarantined_at} is already recorded; two entries sharing "
            "a cell and an instant cannot be told apart by a recovery that names one of them"
        )
    entry = {
        "schema_version": policy["verdict_schema_versions"]["quarantine"],
        "route_id": args.route_id,
        "task_class": args.task_class,
        "cause": args.cause,
        "quarantined_at": quarantined_at,
        "observed_provider": args.observed_provider,
        "observed_model_id": args.observed_model_id,
        "detail": args.detail,
    }
    # Appended beside the last-good generation rather than replacing it: Decision 40 keeps a
    # quarantined cell VISIBLE and non-dispatchable, and a deleted history cannot be reviewed.
    return updated_store(store, policy, quarantines=[*store["quarantines"], entry]), EXIT_OK


def recover_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    policy = load_policy()
    store = load_store(args.store, policy)
    if args.task_class not in policy["task_classes"]:
        raise InputError(f"{args.task_class} is not one of the eight task classes")
    quarantine = active_quarantine(store, args.route_id, args.task_class)
    if quarantine is None:
        raise InputError(
            f"no unresolved quarantine exists for route {args.route_id} in class {args.task_class}, so "
            "there is nothing to recover"
        )
    if args.acknowledged_cause != quarantine["cause"]:
        raise InputError(
            f"--acknowledged-cause {args.acknowledged_cause!r} does not name this quarantine's own "
            f"cause {quarantine['cause']!r}; recovery requires acknowledging what happened"
        )
    matching = [
        generation
        for generation in cell_generations(store, args.route_id, args.task_class)
        if generation["generation_id"] == args.recovery_generation_id
    ]
    if not matching:
        raise InputError(
            f"the store holds no generation {args.recovery_generation_id} for this cell; recovery "
            "cites a qualification the store can actually show"
        )
    generation = matching[0]
    if generation["verdict"] != "qualified":
        raise InputError(
            "the cited recovery generation is unqualified; re-qualification is the only exit from "
            "quarantine, so an unqualified re-measurement leaves the cell out of service"
        )
    recovered_at = parse_timestamp(args.at, "--at", policy)
    issued_at = parse_timestamp(generation["issued_at"], "the recovery generation issued_at", policy)
    if issued_at <= parse_timestamp(quarantine["quarantined_at"], "the quarantine timestamp", policy):
        raise InputError(
            f"the cited generation was issued at {generation['issued_at']}, not after the quarantine "
            f"at {quarantine['quarantined_at']}; evidence gathered before the failure cannot clear it"
        )
    if recovered_at < issued_at:
        raise InputError("--at precedes the cited generation's own issue time")
    entry = {
        "schema_version": policy["verdict_schema_versions"]["recovery"],
        "route_id": args.route_id,
        "task_class": args.task_class,
        "resolves_quarantined_at": quarantine["quarantined_at"],
        "acknowledged_cause": args.acknowledged_cause,
        "recovery_generation_id": args.recovery_generation_id,
        "recovered_at": format_timestamp(recovered_at, policy),
    }
    return updated_store(store, policy, recoveries=[*store["recoveries"], entry]), EXIT_OK


def updated_store(
    store: dict[str, Any],
    policy: dict[str, Any],
    *,
    quarantines: list[dict[str, Any]] | None = None,
    recoveries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Emit the store the caller would persist, leaving every existing entry byte-identical.

    The transform is returned rather than written. Persisting is the caller's separately authorized
    effect, and a tool that rewrote the store in place would be making a durable change on the
    strength of arguments this surface cannot verify.
    """
    result = {
        "schema_version": store["schema_version"],
        "generations": store["generations"],
        "quarantines": store["quarantines"] if quarantines is None else quarantines,
        "recoveries": store["recoveries"] if recoveries is None else recoveries,
    }
    errors = store_errors(result, policy)
    if errors:
        raise InputError("the transformed store would not be valid: " + "; ".join(errors))
    return result


# ---------------------------------------------------------------------------- front door


EXITS = (
    "Exit codes: 0 a verdict or transformed document was derived -- refusing dispatch is this "
    "command SUCCEEDING at deriving a verdict; 2 a supplied document is unreadable, not JSON, not "
    "what it claims to be, or the arguments are unusable; 1 an unexpected internal failure, "
    "including a stdout that cannot receive the result. This command causes no effect: it writes no "
    "file, runs no subprocess, and reaches no network."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="route_qualification.py",
        description=__doc__,
        epilog=EXITS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    issue = commands.add_parser(
        "issue",
        help="Issue one immutable qualification generation from recorded evidence",
        epilog=EXITS,
    )
    issue.add_argument("--evidence", required=True, help=f"one {EVIDENCE_SCHEMA} document")
    issue.add_argument("--route-id", required=True, help="the exact route tuple digest to qualify")
    issue.add_argument("--task-class", required=True, help="one of the eight task classes")
    issue.add_argument("--issued-at", required=True, help="the issue instant, as %%Y-%%m-%%dT%%H:%%M:%%SZ")

    validate = commands.add_parser("validate", help="Check one qualification store", epilog=EXITS)
    validate.add_argument("--store", required=True)

    admit = commands.add_parser(
        "admit",
        help="Derive the pre-dispatch qualification verdict for one exact route/class cell",
        epilog=EXITS,
    )
    admit.add_argument("--store", required=True)
    admit.add_argument("--route-id", required=True)
    admit.add_argument("--task-class", required=True)
    admit.add_argument("--at", required=True, help="the query instant; freshness has no implicit clock")
    admit.add_argument("--observed-provider", default=None, help="the provider identity the caller holds")
    admit.add_argument("--observed-model-id", default=None, help="the model identity the caller holds")
    admit.add_argument(
        "--observed-route-kind",
        default=None,
        help="the gateway route decision, if the caller holds one; default-provider is a quarantine event",
    )

    quarantine = commands.add_parser(
        "quarantine",
        help="Emit the store with one exact route/class cell quarantined",
        epilog=EXITS,
    )
    quarantine.add_argument("--store", required=True)
    quarantine.add_argument("--route-id", required=True)
    quarantine.add_argument("--task-class", required=True)
    quarantine.add_argument("--cause", required=True)
    quarantine.add_argument("--at", required=True)
    quarantine.add_argument("--observed-provider", default=None)
    quarantine.add_argument("--observed-model-id", default=None)
    quarantine.add_argument("--detail", default=None)

    recover = commands.add_parser(
        "recover",
        help="Emit the store with one quarantine resolved by a later qualified generation",
        epilog=EXITS,
    )
    recover.add_argument("--store", required=True)
    recover.add_argument("--route-id", required=True)
    recover.add_argument("--task-class", required=True)
    recover.add_argument("--acknowledged-cause", required=True)
    recover.add_argument("--recovery-generation-id", required=True)
    recover.add_argument("--at", required=True)
    return parser


COMMANDS = {
    "issue": issue_command,
    "validate": validate_command,
    "admit": admit_command,
    "quarantine": quarantine_command,
    "recover": recover_command,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result, code = COMMANDS[args.command](args)
    except InputError as exc:
        print(pretty_json({"status": "refused", "reason": str(exc)}), end="", file=sys.stderr)
        return EXIT_INPUT
    try:
        print(pretty_json(result), end="")
        sys.stdout.flush()
    except OSError:
        # A derived verdict that never reached the caller is not a success.
        return EXIT_INTERNAL
    return code


if __name__ == "__main__":
    raise SystemExit(main())
